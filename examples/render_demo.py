"""Build this repository's public synthetic example from the actual solver."""
import json
from pathlib import Path
from schema_boundary.engine import compare
from schema_boundary.io import read_json
from schema_boundary.report import render_html

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    folder=ROOT/'examples'
    result=compare(read_json(folder/'search.old.json'),read_json(folder/'search.new.json'),domain=read_json(folder/'domain.json'))
    assert result['status']=='counterexample',result['reason']
    result['example']='Synthetic search-tool contract. Demonstration only, not a provider API or production incident.'
    output=ROOT/'docs/demo'; output.mkdir(parents=True,exist_ok=True)
    (output/'report.json').write_bytes((json.dumps(result,indent=2,ensure_ascii=True)+'\n').encode('utf8'))
    (output/'witness.json').write_bytes((result['witness_json']+'\n').encode('utf8'))
    (output/'report.html').write_bytes(render_html(result).encode('utf8'))
    print(json.dumps({'status':result['status'],'witness':result['witness'],'verification':result['verification']}))
