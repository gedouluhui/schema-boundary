"""Run supported official fixtures against the symbolic predicate itself.

Fetch JSON-Schema-Test-Suite separately; it is not bundled with this package.
Every unsupported/out-of-domain case is counted and named, never passed.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import z3
from schema_boundary.domain import Domain
from schema_boundary.io import InputError, Unsupported, loads
from schema_boundary.schema import validate_schema
from schema_boundary.symbolic import Tree

SELECTED=('type','enum','const','minimum','maximum','multipleOf',
          'minLength','maxLength','items','additionalProperties','properties','required','minItems','maxItems',
          'minProperties','maxProperties','allOf','anyOf','oneOf','not','boolean_schema')


def instance_domain(value):
    numbers=[0]; alphabet=set(); keys=set(); length=0; items=0
    def convert(v):
        nonlocal length,items
        if isinstance(v,Decimal):
            if v!=v.to_integral_value(): raise Unsupported('instance contains a nonintegral number')
            v=int(v)
        if type(v) is int: numbers.append(v)
        if type(v) is str: alphabet.update(v); length=max(length,len(v))
        if type(v) is list:
            items=max(items,len(v)); return [convert(x) for x in v]
        if type(v) is dict:
            keys.update(v); return {k:convert(x) for k,x in v.items()}
        return v
    converted=convert(value)
    def depth(v):
        if isinstance(v,dict): return 1+max((depth(x) for x in v.values()),default=0)
        if isinstance(v,list): return 1+max((depth(x) for x in v),default=0)
        return 0
    try:
        domain=Domain(max_depth=depth(converted),max_items=items,max_string=length,
                      alphabet=''.join(sorted(alphabet)) or 'a',integer_min=min(numbers),integer_max=max(numbers),extra_keys=tuple(sorted(keys)))
    except InputError as exc: raise Unsupported('instance domain exceeds configured caps: '+str(exc)) from exc
    return converted,domain


def compatible(constraints):
    # Exact algorithm published by the current official suite's README.
    result=True
    for part in constraints.split(','):
        part=part.strip()
        if part.startswith('<='):
            version=int(part[2:]); result=2020<=version
        elif part.startswith('='):
            version=int(part[1:]); result=2020==version
        else:
            version=int(part); result=2020>=version
        if 2020<=version: break
    return result


def main():
    assert all(compatible(x) is y for x,y in [('6',True),('<=2019',False),('=2020',True),('6,<=2019',False),('=3,7,<=2020',True),('9999',False)])
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('suite',type=Path); p.add_argument('--output',type=Path,default=Path('artifacts/official-verification.json'))
    args=p.parse_args()
    revision=subprocess.check_output(['git','-C',str(args.suite),'rev-parse','HEAD'],text=True).strip()
    records=[]
    for keyword in SELECTED:
        file=args.suite/'validation/tests'/f'{keyword}.json'
        if not file.is_file(): raise AssertionError('missing selected official file: '+keyword)
        # The upstream corpus deliberately includes values outside the product's
        # input budget. Parse the corpus separately; classify each case below.
        groups=json.loads(file.read_text(encoding='utf8'),parse_float=Decimal)['tests']
        for group in groups:
            for case in group['tests']:
                record={'file':keyword,'group':group['description'],'case':case['description']}
                try:
                    if not compatible(group.get('compatibility','2020')):
                        raise Unsupported('fixture does not apply to draft 2020-12')
                    declared=validate_schema(group['schema'])
                    value,domain=instance_domain(case['data'])
                    keys=domain.resolve_keys(declared)
                    tree=Tree(domain,keys)
                    predicate=tree.compile(group['schema'])
                    solver=z3.Solver(ctx=tree.ctx); solver.set(timeout=3000,rlimit=2000000)
                    solver.add(*tree.constraints,tree.equals(value))
                    result=solver.check()
                    if result!=z3.sat: raise AssertionError('official instance unrepresentable: '+str(result))
                    actual=z3.is_true(solver.model().eval(predicate,model_completion=True))
                    if actual is not case['valid']: raise AssertionError('predicate disagrees with official expected value')
                    record.update(status='passed',expected=case['valid'])
                except (Unsupported,InputError) as exc:
                    record.update(status='skipped',reason=str(exc))
                records.append(record)
    counts=dict(Counter(r['status'] for r in records))
    if not counts.get('passed'): raise AssertionError('no official cases ran')
    result={'suite':'json-schema-org/JSON-Schema-Test-Suite','revision':revision,'draft':'2020-12',
            'selected_files':list(SELECTED),'counts':counts,'total':len(records),'cases':records,
            'source_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path('src/schema_boundary').glob('*.py')}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','source_sha256')},indent=2))

if __name__=='__main__': main()
