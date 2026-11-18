import importlib.util
import itertools
import json
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator as V
from schema_boundary.domain import Domain
from test_symbolic import values

class EngineTests(unittest.TestCase):
    def test_interface(self): self.assertIsNotNone(importlib.util.find_spec('schema_boundary.engine'))

    def compare(self,old,new,**kwargs):
        from schema_boundary.engine import compare
        return compare(old,new,**kwargs)

    def test_required_break_has_serialized_independent_witness(self):
        old={'type':'object','additionalProperties':False}
        new={'type':'object','required':['x']}
        result=self.compare(old,new)
        self.assertEqual(result['status'],'counterexample')
        self.assertEqual(result['witness'],{})
        w=json.loads(result['witness_json'])
        self.assertTrue(V(old).is_valid(w)); self.assertFalse(V(new).is_valid(w))
        self.assertTrue(result['verification']['source_accepts'])
        self.assertFalse(result['verification']['target_accepts'])
        self.assertEqual(result['failures'][0]['schema_path'],'/required')

    def test_null_is_real_witness(self):
        r=self.compare({'const':None},False)
        self.assertEqual(r['status'],'counterexample')
        self.assertEqual(r['witness_json'],'null')

    def test_vacuity_and_bounded_compatible(self):
        self.assertEqual(self.compare(False,True)['status'],'empty-source')
        self.assertEqual(self.compare({'type':'integer','minimum':0},{'type':'integer'})['status'],'bounded-compatible')
        self.assertEqual(self.compare(True,True)['status'],'bounded-compatible')

    def test_bounds_never_masquerade_as_universal(self):
        old={'type':'integer'}; new={'type':'integer','maximum':2}
        d=Domain(max_depth=0,integer_min=0,integer_max=2)
        r=self.compare(old,new,domain=d)
        self.assertEqual(r['status'],'bounded-compatible')
        self.assertIn('not a universal',r['reason'])
        r=self.compare(old,new,domain=Domain(max_depth=0,integer_min=0,integer_max=3))
        self.assertEqual(r['status'],'counterexample'); self.assertEqual(r['witness'],3)

    def test_unsupported_even_unreachable_is_unknown(self):
        for schema in ({'allOf':[False,{'pattern':'x'}]}, {'properties':{'x':{'format':'uri'}}}):
            r=self.compare(schema,True)
            self.assertEqual(r['status'],'unknown'); self.assertIn('unsupported',r['reason'])

    def test_real_resource_exhaustion_unknown(self):
        r=self.compare({'type':'object','required':['a']},{'const':None},rlimit=1)
        self.assertEqual(r['status'],'unknown')
        self.assertTrue(r['reason'])
        self.assertIsNone(r['witness'])

    def test_bad_decoded_witness_rejected_not_reported(self):
        from schema_boundary.symbolic import Tree
        with patch.object(Tree,'decode',return_value='not-an-integer'):
            r=self.compare({'type':'integer'},False)
        self.assertEqual(r['status'],'unknown')
        self.assertIn('independent',r['reason'])

    def test_added_open_key_and_nested_containers(self):
        old={'type':'object','required':['x'],'properties':{'x':{'type':'array','items':{'type':'integer'},'minItems':1}}}
        new={'type':'object','properties':{'x':{'items':{'minimum':1}}}}
        r=self.compare(old,new)
        self.assertEqual(r['status'],'counterexample')
        self.assertTrue(V(old).is_valid(r['witness'])); self.assertFalse(V(new).is_valid(r['witness']))
        r=self.compare({'type':'object'},{'type':'object','additionalProperties':False})
        self.assertTrue(r['witness'])

    def test_pairwise_decisions_vs_exhaustive_oracle(self):
        schemas=[False, True, {'type':'integer'}, {'type':'boolean'}, {'const':True}, {'const':1},
                 {'not':{'minimum':0}}, {'oneOf':[{'type':'integer'},{'maximum':0}]}, {'minLength':1}]
        d=Domain(max_depth=0,max_string=1,alphabet='a',integer_min=-1,integer_max=1,extra_keys=())
        all_values=list(values(d,()))
        for old,new in itertools.product(schemas,repeat=2):
            valid=[v for v in all_values if V(old).is_valid(v)]
            broken=[v for v in valid if not V(new).is_valid(v)]
            expect='empty-source' if not valid else ('counterexample' if broken else 'bounded-compatible')
            with self.subTest(old=old,new=new):
                self.assertEqual(self.compare(old,new,domain=d)['status'],expect)

    def test_integer_schema_numeric_lexemes_equivalent(self):
        from schema_boundary.io import loads
        for key in ('minLength','maxLength','minItems','maxItems','minProperties','maxProperties'):
            a=self.compare(loads('{"'+key+'":0.0}'),False)
            b=self.compare({key:0},False)
            self.assertEqual(a['status'],b['status'],key)
            self.assertEqual(a['status'],'counterexample')

    def test_schema_annotations_never_leak_in_failure_messages(self):
        for new in ({'not':{'description':'PRIVATE_ANNOTATION'}},
                    {'oneOf':[{'description':'PRIVATE_ANNOTATION'},True]}):
            report=self.compare({'const':1},new)
            self.assertEqual(report['status'],'counterexample')
            self.assertNotIn('PRIVATE_ANNOTATION',json.dumps(report))

    def test_invalid_schema_diagnostic_does_not_echo_values(self):
        r=self.compare({'type':{'description':'PRIVATE_ANNOTATION'}},True)
        self.assertEqual(r['status'],'error')
        self.assertNotIn('PRIVATE_ANNOTATION',json.dumps(r))

    def test_invalid_domain_and_solver_budgets(self):
        for kwargs in ({'timeout_ms':0},{'rlimit':True},{'domain':{'bad':1}}):
            self.assertEqual(self.compare(True,True,**kwargs)['status'],'error')
        self.assertEqual(self.compare({'type':'nope'},True)['status'],'error')

if __name__=='__main__': unittest.main()
