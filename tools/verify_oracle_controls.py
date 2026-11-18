"""Calibrate the official-corpus adapter against constant wrong predicates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import z3

ROOT=Path(__file__).resolve().parents[1]


def main():
    suite=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'artifacts/official-suite'
    adapter=ROOT/'tools/verify_official.py'
    spec=importlib.util.spec_from_file_location('official_adapter',adapter)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    outcomes=[]
    original=sys.argv
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for wrong in (True,False):
                output=Path(tmp)/f'bad-{wrong}.json'
                sys.argv=['adapter',str(suite),'--output',str(output)]
                with patch.object(module.Tree,'compile',lambda self,schema,node=None:z3.BoolVal(wrong,ctx=self.ctx)):
                    try: module.main()
                    except AssertionError as exc:
                        if 'predicate disagrees with official expected value' not in str(exc): raise
                    else: raise AssertionError('constant wrong predicate was not caught')
                if output.exists(): raise AssertionError('bad predicate wrote a passing official report')
                outcomes.append({'forced_predicate':wrong,'caught_by_official_answer':True,'passing_report_written':False})
    finally: sys.argv=original
    result={'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),'controls':outcomes}
    (ROOT/'artifacts/oracle-controls.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
