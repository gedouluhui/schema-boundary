import copy
import hashlib
import time
import unittest
from unittest.mock import patch

import z3

from schema_boundary.domain import Domain
from schema_boundary.engine import compare
from schema_boundary.io import canonical
from schema_boundary.proof import replay_unsat, serialize_evidence


class UnsatGateTests(unittest.TestCase):
    def compare(self, source=True, target=True):
        return compare(source, target, domain={'max_depth': 0, 'extra_keys': ()})

    def test_bounded_compatible_has_independent_fresh_context_evidence(self):
        result = self.compare({'type': 'integer', 'minimum': 0}, {'type': 'integer'})
        self.assertEqual(result['status'], 'bounded-compatible')
        self.assertIn('not a universal', result['reason'])
        evidence = result['proof']
        self.assertEqual(set(evidence), {'format', 'encoder', 'domain', 'source', 'target', 'canonical_sha256'})
        self.assertEqual(evidence['format'], 'schema-boundary-proof-v1')
        self.assertEqual(evidence['encoder'], 'tree-v1')
        self.assertEqual(evidence['domain']['integer_min'], -16)
        self.assertEqual(evidence['domain']['integer_max'], 16)
        self.assertEqual(result['verification']['unsat_replay']['status'], 'unsat')
        self.assertTrue(replay_unsat(evidence, timeout_ms=1000))
        changed = copy.deepcopy(evidence)
        changed['domain']['integer_max'] += 1
        with self.assertRaises(ValueError):
            replay_unsat(changed, timeout_ms=1000)

    def test_replay_recompiles_validated_domain_and_schemas(self):
        domain = Domain(max_depth=0, max_items=0, max_string=1, extra_keys=())
        source = {'type': 'integer', 'minimum': 0}
        target = {'type': 'integer'}
        evidence = serialize_evidence(domain, source, target)
        self.assertTrue(replay_unsat(evidence, timeout_ms=1000))
        self.assertEqual(set(evidence['domain']), {
            'max_depth', 'max_items', 'max_string', 'alphabet',
            'integer_min', 'integer_max', 'extra_keys',
        })

    def test_proof_strips_annotations_only_at_schema_positions(self):
        literal = {
            'description': 'literal-description',
            'title': 'literal-title',
            'default': 'literal-default',
            'examples': ['literal-examples'],
        }
        schema = {
            'type': 'object',
            'description': 'PRIVATE_SOURCE_DESCRIPTION',
            'title': 'PRIVATE_SOURCE_TITLE',
            'default': {'private': 'PRIVATE_SOURCE_DEFAULT'},
            'examples': [{'private': 'PRIVATE_SOURCE_EXAMPLES'}],
            'properties': {
                'payload': {
                    'description': 'PRIVATE_NESTED_DESCRIPTION',
                    'anyOf': [
                        {'const': literal, 'title': 'PRIVATE_BRANCH_TITLE'},
                        {'enum': [literal], 'description': 'PRIVATE_ENUM_DESCRIPTION'},
                    ],
                },
            },
            'additionalProperties': False,
        }
        result = compare(schema, schema)
        self.assertEqual(result['status'], 'bounded-compatible')
        evidence = result['proof']
        self.assertEqual(set(evidence['source']), {'type', 'properties', 'additionalProperties'})
        self.assertEqual(set(evidence['target']), {'type', 'properties', 'additionalProperties'})
        payload = evidence['source']['properties']['payload']
        self.assertEqual(set(payload), {'anyOf'})
        const_branch, enum_branch = payload['anyOf']
        self.assertEqual(set(const_branch), {'const'})
        self.assertEqual(set(enum_branch), {'enum'})
        self.assertEqual(const_branch['const'], literal)
        self.assertEqual(enum_branch['enum'], [literal])
        self.assertNotIn('PRIVATE_', canonical(evidence))
        self.assertTrue(replay_unsat(evidence, timeout_ms=1000))

    def test_missing_domain_field_is_malformed_even_with_valid_digest(self):
        evidence = self.compare({'type': 'integer'}, {'type': 'integer'})['proof']
        del evidence['domain']['integer_max']
        evidence['canonical_sha256'] = hashlib.sha256(canonical({
            key: value for key, value in evidence.items() if key != 'canonical_sha256'
        }).encode('utf8')).hexdigest()
        with self.assertRaises(ValueError):
            replay_unsat(evidence, timeout_ms=1000)

    def test_forged_self_consistent_satisfiable_evidence_is_rejected(self):
        domain = Domain(max_depth=0, max_items=0, max_string=1, extra_keys=())
        forged = serialize_evidence(domain, {'type': 'integer'}, False)
        self.assertFalse(replay_unsat(forged, timeout_ms=1000))

    def test_injected_assertion_and_smt_fields_are_rejected(self):
        evidence = self.compare({'type': 'integer'}, {'type': 'integer'})['proof']
        injections = (
            {'assertions': ['(assert false)']},
            {'source_predicate': 'false'},
            {'target_predicate': 'true'},
            {'declarations': []},
            {'smt2': '(check-sat)'},
        )
        for injection in injections:
            with self.subTest(injection=injection), self.assertRaises(ValueError):
                replay_unsat(evidence | injection, timeout_ms=1000)

    def test_schema_text_cannot_inject_smt_commands(self):
        evidence = self.compare({'type': 'integer'}, {'type': 'integer'})['proof']
        evidence['source'] = '(check-sat)\n(assert false)'
        evidence['canonical_sha256'] = hashlib.sha256(canonical({
            key: value for key, value in evidence.items() if key != 'canonical_sha256'
        }).encode('utf8')).hexdigest()
        with self.assertRaises(ValueError):
            replay_unsat(evidence, timeout_ms=1000)

    def test_replay_parsing_overrun_never_invokes_solver(self):
        from schema_boundary import proof

        evidence = self.compare({'type': 'integer'}, {'type': 'integer'})['proof']

        def slow_normalize(value):
            time.sleep(0.03)
            return value

        with patch.object(proof, 'normalize', side_effect=slow_normalize), \
             patch.object(proof.z3, 'Solver', side_effect=AssertionError('solver invoked')):
            with self.assertRaises(TimeoutError):
                replay_unsat(evidence, timeout_ms=1)

    def test_replay_deadline_overrun_prevents_solver_check(self):
        from schema_boundary import proof

        evidence = self.compare({'type': 'integer'}, {'type': 'integer'})['proof']
        clock = [100.0]
        checks = []

        class FakeSolver:
            def __init__(self, **kwargs):
                pass

            def set(self, **kwargs):
                pass

            def add(self, *args):
                clock[0] += 0.04

            def check(self):
                checks.append(True)
                return z3.unsat

        with patch.object(proof.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(proof.z3, 'Solver', FakeSolver):
            with self.assertRaises(TimeoutError):
                replay_unsat(evidence, timeout_ms=30, deadline=clock[0] + 0.03)
        self.assertEqual(checks, [])

    def test_replay_unavailable_downgrades_compatibility(self):
        with patch('schema_boundary.engine.replay_unsat', side_effect=RuntimeError('unavailable')):
            result = self.compare()
        self.assertEqual(result['status'], 'unknown')
        self.assertIn('independent UNSAT replay unavailable', result['reason'])
        self.assertIsNone(result['proof'])

    def test_replay_must_prove_unsat(self):
        result = self.compare({'type': 'integer', 'minimum': 0}, {'type': 'integer'})
        with patch('schema_boundary.engine.replay_unsat', return_value=False):
            unavailable = self.compare()
        self.assertEqual(unavailable['status'], 'unknown')
        self.assertIn('independent UNSAT replay unavailable', unavailable['reason'])
        with self.assertRaises(ValueError):
            replay_unsat(result['proof'] | {'target': True}, timeout_ms=1000)

    def test_replay_exhaustion_downgrades_compatibility(self):
        with patch('schema_boundary.engine.replay_unsat', side_effect=TimeoutError('deadline')):
            result = self.compare()
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'total_deadline')

    def test_counterexamples_keep_existing_independent_verification(self):
        result = self.compare({'type': 'integer'}, False)
        self.assertEqual(result['status'], 'counterexample')
        self.assertTrue(result['verification']['roundtrip_checked'])
        self.assertTrue(result['verification']['source_accepts'])
        self.assertFalse(result['verification']['target_accepts'])
        self.assertIsNone(result['proof'])


if __name__ == '__main__':
    unittest.main()
