"""Build first, then verify the real wheel in a clean environment outside source.

Pass --wheelhouse for offline dependency installation, or use the configured pip
index. No user environment is changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--wheelhouse',type=Path); args=p.parse_args()
    wheels=list((ROOT/'dist').glob('schema_boundary-*.whl'))
    if len(wheels)!=1: raise AssertionError('expected one product wheel')
    wheel=wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        for source in (ROOT/'src/schema_boundary').glob('*.py'):
            if archive.read('schema_boundary/'+source.name)!=source.read_bytes(): raise AssertionError('wheel differs from reviewed source: '+source.name)
    with tempfile.TemporaryDirectory(prefix='schema-boundary-install-') as folder:
        work=Path(folder); venv.EnvBuilder(with_pip=True).create(work/'venv')
        python=work/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
        def run(*parts,expected=0):
            result=subprocess.run([str(python),'-I',*map(str,parts)],cwd=work,env=env,capture_output=True,text=True,encoding='utf8',timeout=120)
            if result.returncode!=expected: raise AssertionError(f'expected {expected}, got {result.returncode}: {result.stdout}\n{result.stderr}')
            return result.stdout
        options=['--no-index','--find-links',str(args.wheelhouse.resolve())] if args.wheelhouse else []
        run('-m','pip','install',*options,wheel)
        imported=run('-c','import schema_boundary; print(schema_boundary.__file__)').strip()
        if str(work/'venv') not in imported: raise AssertionError('import did not come from installed package')
        old=ROOT/'examples/search.old.json'; new=ROOT/'examples/search.new.json'; relaxed=ROOT/'examples/search.relaxed.json'; domain=ROOT/'examples/domain.json'
        results=[]
        for target,flags,expected,status in [(new,[],1,'counterexample'),(relaxed,[],3,'bounded-compatible'),
            (relaxed,['--accept-bounded'],0,'bounded-compatible'),(ROOT/'examples/unsupported.json',[],2,'unknown')]:
            data=json.loads(run('-m','schema_boundary','compare',old,target,'--domain',domain,*flags,expected=expected))
            if data['status']!=status: raise AssertionError('wrong installed status')
            results.append({'expected_exit':expected,'actual_status':data['status']})
        report=json.loads(run('-m','schema_boundary','compare',old,new,'--domain',domain,'--output',work/'case',expected=1))
        witness=(work/'case/witness.json').read_text(encoding='utf8').strip()
        if witness!=report['witness_json']: raise AssertionError('written witness differs')
        run('-m','schema_boundary','compare',old,new,'--output',work/'case',expected=2)
        empty=work/'empty-source.json'; empty.write_text('false',encoding='utf8')
        empty_result=json.loads(run('-m','schema_boundary','compare',empty,new,expected=4))
        if empty_result['status']!='empty-source': raise AssertionError('vacuity misclassified')
        results.append({'expected_exit':4,'actual_status':empty_result['status']})
        run('-c','import json,sys; from jsonschema import Draft202012Validator as V; source,target,witness=(json.load(open(p,encoding="utf8")) for p in sys.argv[1:]); assert V(source).is_valid(witness) and not V(target).is_valid(witness)',old,new,work/'case/witness.json')
        versions=json.loads(run('-c','import json,importlib.metadata as m; print(json.dumps({n:m.version(n) for n in ["z3-solver","jsonschema"]}))'))
        result={'wheel':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),
                'clean_venv':True,'isolated_python':True,'outside_source_tree':True,'installed_dependencies':versions,
                'cases':results,'witness_roundtrip':True,'existing_output_rejected':True,'wheel_source_match':True}
    (ROOT/'artifacts/install-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
