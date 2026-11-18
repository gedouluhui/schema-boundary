"""Small synthetic timing measurements, not a comparative performance claim."""
import hashlib
import json
from pathlib import Path
import platform
import time
from schema_boundary.engine import compare
from schema_boundary.domain import Domain
from schema_boundary.io import read_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    old=read_json(ROOT/'examples/search.old.json')
    new=read_json(ROOT/'examples/search.new.json')
    d=read_json(ROOT/'examples/domain.json')
    jobs=[('synthetic-tool-breaking',old,new,d,'counterexample'),
          ('synthetic-tool-relaxed',old,read_json(ROOT/'examples/search.relaxed.json'),d,'bounded-compatible'),
          ('wide-integer-interval',{'type':'integer'},{'type':'integer','maximum':999999999999},
           Domain(max_depth=0,integer_min=0,integer_max=10**12),'counterexample')]
    rows=[]
    for name,source,target,domain,expected in jobs:
        for repetition in range(3):
            start=time.perf_counter(); result=compare(source,target,domain=domain); elapsed=time.perf_counter()-start
            if result['status']!=expected: raise AssertionError((name,result))
            rows.append({'scenario':name,'repetition':repetition+1,'seconds':elapsed,'status':result['status'],'stats':result['stats']})
    result={'provenance':'maintainer-local time.perf_counter wall seconds, includes input normalization and compilation; no memory or external baseline measured',
            'platform':platform.system(),'python':platform.python_version(),'engines':result['engines'],'synthetic':True,'runs':rows,
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/schema_boundary').glob('*.py')}}
    (ROOT/'artifacts/benchmark.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'python':result['python'],'engines':result['engines'],'runs':rows},indent=2))

if __name__=='__main__': main()
