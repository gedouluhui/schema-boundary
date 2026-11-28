"""Self-describing bounded-compatibility evidence and independent replay."""
from dataclasses import fields
import hashlib
import math
import time

import z3

from .domain import Domain
from .io import Unsupported, canonical, normalize
from .schema import strip_annotations, validate_schema
from .symbolic import Tree

FORMAT = 'schema-boundary-proof-v1'
ENCODER = 'tree-v1'
_EVIDENCE_FIELDS = {'format', 'encoder', 'domain', 'source', 'target', 'canonical_sha256'}
_DOMAIN_FIELDS = {field.name for field in fields(Domain)}


def _digest(payload):
    return hashlib.sha256(canonical(payload).encode('utf8')).hexdigest()


def serialize_evidence(domain, source, target):
    """Capture validated inputs, never solver assertions or generated SMT text."""
    if not isinstance(domain, Domain):
        raise ValueError('evidence domain must be a Domain')
    domain_payload = {
        field.name: (list(getattr(domain, field.name)) if field.name == 'extra_keys'
                     else getattr(domain, field.name))
        for field in fields(Domain)
    }
    payload = {
        'format': FORMAT,
        'encoder': ENCODER,
        'domain': domain_payload,
        'source': strip_annotations(source),
        'target': strip_annotations(target),
    }
    return {**payload, 'canonical_sha256': _digest(payload)}


def _check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('total_deadline')


def _parse_evidence(evidence):
    if type(evidence) is not dict or set(evidence) != _EVIDENCE_FIELDS:
        raise ValueError('malformed proof evidence fields')
    if evidence['format'] != FORMAT or evidence['encoder'] != ENCODER:
        raise ValueError('unsupported proof format or encoder')
    payload = {key: evidence[key] for key in _EVIDENCE_FIELDS - {'canonical_sha256'}}
    digest = evidence['canonical_sha256']
    if type(digest) is not str or digest != _digest(payload):
        raise ValueError('proof canonical digest mismatch')
    if type(payload['domain']) is not dict or set(payload['domain']) != _DOMAIN_FIELDS:
        raise ValueError('malformed proof domain fields')
    return payload


def replay_unsat(evidence, *, timeout_ms=5000, rlimit=2000000, deadline=None):
    """Independently rebuild and solve ``domain AND source AND NOT target``.

    Evidence contains only the finite domain and normalized schema inputs. All
    symbolic predicates are rebuilt with a fresh ``Tree`` and Z3 context; no
    serialized assertion or SMT source is ever accepted or executed.
    """
    if type(timeout_ms) is not int or timeout_ms <= 0:
        raise ValueError('timeout_ms must be a positive integer')
    if type(rlimit) is not int or rlimit <= 0:
        raise ValueError('rlimit must be a positive integer')
    if deadline is None:
        deadline = time.monotonic() + timeout_ms / 1000
    elif type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('deadline must be a finite monotonic timestamp')

    _check_deadline(deadline)
    payload = _parse_evidence(evidence)
    _check_deadline(deadline)

    domain = Domain.from_dict(payload['domain'])
    _check_deadline(deadline)
    source = normalize(payload['source'])
    _check_deadline(deadline)
    target = normalize(payload['target'])
    _check_deadline(deadline)
    declared = validate_schema(source) | validate_schema(target)
    _check_deadline(deadline)
    keys = domain.resolve_keys(declared)
    _check_deadline(deadline)

    try:
        tree = Tree(domain, keys, deadline=deadline)
        _check_deadline(deadline)
        old = tree.compile(source)
        _check_deadline(deadline)
        new = tree.compile(target)
        _check_deadline(deadline)
    except Unsupported as exc:
        if str(exc) == 'total_deadline':
            raise TimeoutError('total_deadline') from exc
        raise

    solver = z3.Solver(ctx=tree.ctx)
    remaining_ms = max(1, math.ceil((deadline - time.monotonic()) * 1000))
    solver.set(timeout=remaining_ms, rlimit=rlimit, random_seed=0)
    solver.add(*tree.constraints, old, z3.Not(new))
    _check_deadline(deadline)
    result = solver.check()
    _check_deadline(deadline)
    return result == z3.unsat
