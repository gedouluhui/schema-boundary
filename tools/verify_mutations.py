"""Known-bad variants in disposable source copies; never mutate the workspace."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CASES=[
 ('required-ignored','symbolic.py',"for key in schema.get('required',[]):",'for key in []:', 'test_symbolic.py','test_exhaustive_predicates_against_independent_validator'),
 ('additional-properties-open','symbolic.py',"else schema.get('additionalProperties',True)",'else True','test_symbolic.py','test_exhaustive_predicates_against_independent_validator'),
 ('oneof-as-anyof','symbolic.py','for child in children])==1)','for child in children])>=1)','test_symbolic.py','test_exhaustive_predicates_against_independent_validator'),
 ('minimum-exclusive','symbolic.py',"'minimum':lambda:n.number>=bound","'minimum':lambda:n.number>bound",'test_symbolic.py','test_exhaustive_predicates_against_independent_validator'),
 ('independent-gate-disabled','engine.py','if not source_ok or not in_domain:','if False:', 'test_engine.py','test_bad_decoded_witness_rejected_not_reported'),
 ('unsupported-ignored','schema.py','if unknown: raise Unsupported','if False: raise Unsupported','test_engine.py','test_unsupported_even_unreachable_is_unknown'),
]


def main():
    snapshots={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/schema_boundary').glob('*.py')}
    outcomes=[]
    with tempfile.TemporaryDirectory(prefix='schema-boundary-mutations-') as tmp:
        copy=Path(tmp)
        shutil.copytree(ROOT/'src',copy/'src',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'tests',copy/'tests',ignore=shutil.ignore_patterns('__pycache__'))
        env={**os.environ,'PYTHONPATH':str(copy/'src'),'PYTHONUTF8':'1'}
        def run(suite):
            return subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],
                cwd=copy,env=env,capture_output=True,text=True,encoding='utf8',timeout=90)
        for suite in sorted({c[4] for c in CASES}):
            r=run(suite)
            if r.returncode: raise AssertionError('baseline failed '+suite+'\n'+r.stdout+r.stderr)
        for name,file,old,new,suite,test in CASES:
            target=copy/'src/schema_boundary'/file
            raw=target.read_text(encoding='utf8')
            if raw.count(old)!=1: raise AssertionError('mutation anchor not unique: '+name)
            changed=raw.replace(old,new)
            if raw==changed: raise AssertionError('no-op mutation: '+name)
            try:
                target.write_text(changed,encoding='utf8',newline='\n')
                shutil.rmtree(target.parent/'__pycache__',ignore_errors=True)
                r=run(suite)
                caught=r.returncode==1 and 'FAIL: '+test in (r.stdout+r.stderr)
                if not caught: raise AssertionError('mutation not caught by named assertion: '+name+'\n'+r.stdout+r.stderr)
                outcomes.append({'mutation':name,'test':test,'caught':True})
            finally:
                target.write_text(raw,encoding='utf8',newline='\n')
                shutil.rmtree(target.parent/'__pycache__',ignore_errors=True)
    if snapshots!={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src/schema_boundary').glob('*.py')}:
        raise AssertionError('workspace source changed; evidence is stale')
    result={'source_sha256':snapshots,'cases':outcomes,'caught':len(outcomes),'total':len(CASES)}
    (ROOT/'artifacts').mkdir(exist_ok=True)
    (ROOT/'artifacts/mutation-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
