"""Bounded source-minus-target solver with serialized-witness and UNSAT gates."""
import importlib.metadata
import json
import math
import time
import z3
from jsonschema import Draft202012Validator
from .domain import Domain
from .io import InputError, Unsupported, normalize, fingerprint
from .proof import replay_unsat, serialize_evidence
from .schema import validate_schema
from .symbolic import Tree


def _pointer(path):
    return ''.join('/'+str(p).replace('~','~0').replace('/','~1') for p in path)


def _roundtrip(tree,model,domain,keys,source,target=None):
    raw=json.dumps(tree.decode(model),ensure_ascii=True,allow_nan=False,separators=(',',':'),sort_keys=True)
    witness=json.loads(raw)
    source_ok=Draft202012Validator(source).is_valid(witness)
    in_domain=domain.contains(witness,keys)
    if not source_ok or not in_domain:
        raise Unsupported('independent serialized-witness validation disagrees with solver: source/domain')
    target_errors=[] if target is None else list(Draft202012Validator(target).iter_errors(witness))
    if target is not None and not target_errors:
        raise Unsupported('independent serialized-witness validation disagrees with solver: target accepts')
    failures=[{'instance_path':_pointer(e.absolute_path),'schema_path':_pointer(e.absolute_schema_path),
               'keyword':str(e.validator),'message':'Target constraint failed: '+str(e.validator)} for e in target_errors]
    return witness,raw,failures


def compare(source,target,*,domain=None,timeout_ms=5000,rlimit=2000000):
    """Find source-valid / target-invalid JSON inside the reported finite domain.

    No result proves compatibility for inputs outside the finite universe. A null
    counterexample is distinguishable via status and witness_json='null'.
    """
    report={'schema_version':1,'direction':'source-minus-target','status':'unknown','reason':'not started',
            'domain':None,'limits':{},'hashes':{},'witness':None,'witness_json':None,'proof':None,
            'verification':None,'failures':[],'stats':{},
            'engines':{'z3':z3.get_version_string(),'jsonschema':importlib.metadata.version('jsonschema')}}
    deadline=time.monotonic()+timeout_ms/1000 if type(timeout_ms) in (int,float) else time.monotonic()

    def remaining():
        left=deadline-time.monotonic()
        if left<=0: raise Unsupported('total_deadline')
        return left

    def check_phase():
        left=remaining()
        return max(1,math.ceil(left*1000))

    try:
        for value,label,maximum in ((timeout_ms,'timeout_ms',60000),(rlimit,'rlimit',50000000)):
            if type(value) is not int or not 1<=value<=maximum: raise InputError(f'{label} must be an integer in [1,{maximum}]')
        deadline=time.monotonic()+timeout_ms/1000
        report['limits']={'timeout_ms_total':timeout_ms,'timeout_ms_per_check':timeout_ms,'rlimit_per_check':rlimit,'max_symbolic_nodes':3000,'max_compile_work_units':25000}
        remaining()
        d=Domain() if domain is None else (domain if isinstance(domain,Domain) else Domain.from_dict(domain))
        check_phase()
        source,target=normalize(source),normalize(target)
        check_phase()
        report['hashes']={'source_canonical_sha256':fingerprint(source),'target_canonical_sha256':fingerprint(target)}
        declared=validate_schema(source)|validate_schema(target)
        check_phase()
        keys=d.resolve_keys(declared)
        report['domain']=d.to_dict(keys)
        check_phase()
        tree=Tree(d,keys,deadline=deadline)
        old,new=tree.compile(source),tree.compile(target)
        check_phase()
        report['stats']={'symbolic_nodes':tree.nodes,'compile_work_units':tree.visits,'domain_constraints':len(tree.constraints)}
        solver=z3.Solver(ctx=tree.ctx)
        solver.set(timeout=check_phase(),rlimit=rlimit,random_seed=0)
        solver.add(*tree.constraints,old)
        result=solver.check()
        check_phase()
        if result==z3.unknown:
            raise Unsupported('source satisfiability unknown: '+solver.reason_unknown())
        if result==z3.unsat:
            report.update(status='empty-source',reason='Source has no instances in this finite domain; do not interpret vacuity as compatibility.')
            return report
        _roundtrip(tree,solver.model(),d,keys,source)
        check_phase()
        report['verification']={'source_nonempty_in_domain':True}
        solver.add(z3.Not(new))
        solver.set(timeout=check_phase())
        result=solver.check()
        check_phase()
        if result==z3.unknown:
            raise Unsupported('difference search unknown: '+solver.reason_unknown())
        if result==z3.unsat:
            evidence=serialize_evidence(report['domain'],tree.constraints,source,target,old,new)
            check_phase()
            try:
                replayed=replay_unsat(evidence,timeout_ms=check_phase(),rlimit=rlimit)
            except (Unsupported, TimeoutError):
                raise
            except Exception as exc:
                raise Unsupported('independent UNSAT replay unavailable: '+type(exc).__name__) from exc
            check_phase()
            if not replayed:
                raise Unsupported('independent UNSAT replay unavailable: replay did not prove unsat')
            evidence['replay']={'status':'unsat','context':'fresh','encoding':'z3-smt2-v1'}
            report['proof']=evidence
            report.update(status='bounded-compatible',reason='No source-minus-target counterexample in the stated domain; not a universal compatibility guarantee.')
            return report
        witness,raw,failures=_roundtrip(tree,solver.model(),d,keys,source,target)
        check_phase()
        report.update(status='counterexample',reason='Serialized JSON independently accepted by source and rejected by target.',
            witness=witness,witness_json=raw,failures=failures,
            verification={'source_nonempty_in_domain':True,'roundtrip_checked':True,'domain_contains':True,'source_accepts':True,'target_accepts':False})
    except (InputError, TimeoutError) as exc:
        report.update(status='error' if isinstance(exc, InputError) else 'unknown',
                      reason='total_deadline' if isinstance(exc, TimeoutError) else str(exc))
    except Unsupported as exc:
        report.update(status='unknown',reason=str(exc),witness=None,witness_json=None,failures=[])
    except (z3.Z3Exception,RecursionError,ArithmeticError,ValueError,TypeError,KeyError,IndexError) as exc:
        report.update(status='unknown',reason='solver or independent verification could not complete: '+type(exc).__name__,witness=None,witness_json=None,failures=[])
    return report
