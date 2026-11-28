import copy
import unittest
from unittest.mock import patch

from schema_boundary.engine import compare
from schema_boundary.proof import replay_unsat


class UnsatGateTests(unittest.TestCase):
    def compare(self, source=True, target=True):
        return compare(source, target, domain={'max_depth': 0, 'extra_keys': ()})

    def test_bounded_compatible_has_independent_fresh_context_evidence(self):
        result = self.compare({'type': 'integer', 'minimum': 0}, {'type': 'integer'})
        self.assertEqual(result['status'], 'bounded-compatible')
        self.assertIn('not a universal', result['reason'])
        evidence = result['proof']
        self.assertEqual(evidence['format'], 'z3-smt2-v1')
        self.assertEqual(evidence['domain']['numbers'], 'integers only')
        self.assertEqual(evidence['replay']['status'], 'unsat')
        self.assertTrue(replay_unsat(evidence, timeout_ms=1000))
        changed = copy.deepcopy(evidence)
        changed['domain']['integer_max'] += 1
        with self.assertRaises(ValueError):
            replay_unsat(changed, timeout_ms=1000)

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
