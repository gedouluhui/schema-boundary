import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]

class CLIReportTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.old=self.root/'old.json'; self.new=self.root/'new.json'
        self.old.write_text('{"type":"object","additionalProperties":false}')
        self.new.write_text('{"type":"object","required":["x"]}')
    def cli(self,*args):
        return subprocess.run([sys.executable,'-m','schema_boundary',*map(str,args)],cwd=self.root,
            env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True,encoding='utf8',timeout=30)
    def test_counterexample_and_files(self):
        out=self.root/'case'
        r=self.cli('compare',self.old,self.new,'--output',out)
        self.assertEqual(r.returncode,1,r.stderr)
        self.assertTrue(r.stdout.strip(),'CLI must emit JSON')
        data=json.loads(r.stdout)
        self.assertEqual(data['status'],'counterexample')
        self.assertEqual(json.loads((out/'witness.json').read_text()),{})
        self.assertEqual(json.loads((out/'report.json').read_text()),data)
        self.assertIn('Source accepts', (out/'report.html').read_text(encoding='utf8'))
    def test_bounded_fail_closed_requires_explicit_optin(self):
        self.new.write_text('true')
        r=self.cli('compare',self.old,self.new)
        self.assertEqual(r.returncode,3,r.stderr)
        self.assertEqual(json.loads(r.stdout)['status'],'bounded-compatible')
        self.assertEqual(self.cli('compare',self.old,self.new,'--accept-bounded').returncode,0)
    def test_empty_and_unsupported(self):
        self.old.write_text('false')
        self.assertEqual(self.cli('compare',self.old,self.new).returncode,4)
        self.old.write_text('{"pattern":"x"}')
        r=self.cli('compare',self.old,self.new)
        self.assertEqual(r.returncode,2)
        self.assertEqual(json.loads(r.stdout)['status'],'unknown')
    def test_existing_output_never_overwritten(self):
        out=self.root/'case'; out.mkdir(); original=out/'keep'; original.write_bytes(b'untouched')
        r=self.cli('compare',self.old,self.new,'--output',out)
        self.assertEqual(r.returncode,2)
        self.assertEqual(json.loads(r.stdout)['status'],'error')
        self.assertEqual(list(out.iterdir()),[original]); self.assertEqual(original.read_bytes(),b'untouched')
        before=self.old.read_bytes()
        self.assertEqual(self.cli('compare',self.old,self.new,'--output',self.old).returncode,2)
        self.assertEqual(self.old.read_bytes(),before)
    def test_null_witness_file(self):
        self.old.write_text('{"const":null}'); self.new.write_text('false')
        r=self.cli('compare',self.old,self.new,'--output',self.root/'null')
        self.assertEqual(r.returncode,1)
        self.assertEqual((self.root/'null/witness.json').read_text().strip(),'null')
    def test_invalid_args_and_budget(self):
        for args in ((),('nope',),('compare',self.old,self.new,'--rlimit','abc')):
            r=self.cli(*args)
            self.assertEqual(r.returncode,2)
            self.assertEqual(json.loads(r.stdout)['status'],'error')
        r=self.cli('compare',self.old,self.new,'--rlimit',1)
        self.assertEqual(r.returncode,2)
        self.assertEqual(json.loads(r.stdout)['status'],'unknown')
    def test_example_label_is_escaped(self):
        from schema_boundary.report import render_html
        r={'status':'unknown','reason':'no result','example':'Synthetic <fixture>'}
        self.assertIn('Synthetic &lt;fixture&gt;',render_html(r))

    def test_report_escape_and_status_labels(self):
        from schema_boundary.report import render_html
        attack='</pre><img src=x onerror=alert(1)>'
        class Tags(HTMLParser):
            def __init__(self): super().__init__(); self.tags=[]
            def handle_starttag(self,tag,attrs): self.tags.append((tag,dict(attrs)))
        for status in ('counterexample','bounded-compatible','empty-source','unknown','error'):
            html=render_html({'status':status,'reason':attack,'witness_json':attack,'domain':{'alphabet':attack}})
            p=Tags(); p.feed(html)
            self.assertFalse(any(t in ('script','img','iframe','link') for t,a in p.tags))
            self.assertIn('&lt;img',html)
            self.assertIn('Finite domain',html)
            self.assertNotIn('Universal compatibility verified',html)

if __name__=='__main__': unittest.main()
