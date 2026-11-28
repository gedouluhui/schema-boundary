"""Serialized bounded-compatibility evidence and independent fresh-context replay."""
import hashlib

import z3
from z3.z3util import get_vars

from .io import canonical

FORMAT = 'z3-smt2-v1'


def _digest(payload):
    return hashlib.sha256(canonical(payload).encode('utf8')).hexdigest()


def serialize_evidence(domain, constraints, source, target, old, new):
    """Capture exactly the assertions used by the bounded difference check."""
    assertions = list(constraints) + [old, new]
    variables = {}
    for assertion in assertions:
        for variable in get_vars(assertion):
            variables[variable.decl().name()] = variable
    payload = {
        'format': FORMAT,
        'domain': domain,
        'source': source,
        'target': target,
        'declarations': [
            {'name': name, 'sort': variable.sort().sexpr()}
            for name, variable in sorted(variables.items())
        ],
        'constraints': [assertion.sexpr() for assertion in constraints],
        'source_predicate': old.sexpr(),
        'target_predicate': new.sexpr(),
    }
    return {**payload, 'canonical_sha256': _digest(payload)}


def replay_unsat(evidence, *, timeout_ms=5000, rlimit=2000000):
    """Rebuild serialized assertions in a fresh context and require UNSAT.

    This is deliberately separate from the solver/model that produced the
    original result. Malformed, inconsistent, SAT, or inconclusive evidence is
    never accepted as proof of bounded compatibility.
    """
    if type(timeout_ms) is not int or timeout_ms <= 0:
        raise ValueError('timeout_ms must be a positive integer')
    if type(rlimit) is not int or rlimit <= 0:
        raise ValueError('rlimit must be a positive integer')
    if type(evidence) is not dict or evidence.get('format') != FORMAT:
        raise ValueError('unsupported proof format')
    payload = {key: evidence.get(key) for key in (
        'format', 'domain', 'source', 'target', 'declarations', 'constraints',
        'source_predicate', 'target_predicate')}
    if evidence.get('canonical_sha256') != _digest(payload):
        raise ValueError('proof canonical digest mismatch')
    serialized = ['(declare-fun '+item['name']+' () '+item['sort']+')'
                  for item in payload['declarations']]
    serialized += ['(assert '+assertion+')' for assertion in payload['constraints']]
    serialized += ['(assert '+payload['source_predicate']+')',
                   '(assert (not '+payload['target_predicate']+'))', '(check-sat)']
    text = '\n'.join(serialized)
    ctx = z3.Context()
    solver = z3.Solver(ctx=ctx)
    solver.set(timeout=timeout_ms, rlimit=rlimit, random_seed=0)
    solver.from_string(text)
    return solver.check() == z3.unsat
