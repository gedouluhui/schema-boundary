import importlib.util
from decimal import Decimal
import unittest


class InputTests(unittest.TestCase):
    def test_interfaces_exist(self):
        for name in ('io','domain','schema'):
            self.assertIsNotNone(importlib.util.find_spec('schema_boundary.'+name), name+' not implemented')

    def test_exact_decimal_and_duplicate_keys(self):
        from schema_boundary.io import loads, InputError, canonical
        self.assertEqual(loads('{"minimum":0.1}')['minimum'], Decimal('0.1'))
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '"\\ud800"', '[Infinity]', '[1e99999]'):
            with self.subTest(text=text), self.assertRaises(InputError): loads(text)
        self.assertEqual(canonical({'a':Decimal('1.50'),'b':True}), '{"a":1.50,"b":true}')

    def test_depth_and_schema_errors(self):
        from schema_boundary.io import loads, InputError
        from schema_boundary.schema import validate_schema
        with self.assertRaises(InputError): loads('['*34+'0'+']'*34)
        for schema in ({'type':'fake'}, {'minLength':-1}, {'required':[1]}, {'multipleOf':0}):
            with self.subTest(schema=schema), self.assertRaises(InputError): validate_schema(schema)

    def test_unsupported_positions_not_literal_keys(self):
        from schema_boundary.io import Unsupported
        from schema_boundary.schema import validate_schema
        for schema in ({'not':{'pattern':'x'}}, {'properties':{'x':{'$ref':'https://example.test'}}}, {'$schema':'http://json-schema.org/draft-04/schema#'}):
            with self.subTest(schema=schema), self.assertRaises(Unsupported): validate_schema(schema)
        self.assertEqual(validate_schema({'const':{'pattern':'data'}, 'default':{'unknown':'data'}}), {'pattern'})
        self.assertEqual(validate_schema({'properties':{'x':{}}, 'required':['y']}), {'x','y'})

    def test_domain_validity_and_membership(self):
        from schema_boundary.domain import Domain
        from schema_boundary.io import InputError
        d = Domain(max_depth=1,max_items=1,max_string=1,alphabet='a中',integer_min=-1,integer_max=1)
        for value in (None,True,-1,'中',[],[1],{}, {'x':False}):
            self.assertTrue(d.contains(value, ('x',)), repr(value))
        for value in (2,1.5,'ab',[1,2],[[1]],{'y':1},{'x':[]}):
            self.assertFalse(d.contains(value, ('x',)), repr(value))
        for value in ({'max_depth':True},{'max_items':-1},{'integer_min':2,'integer_max':1},{'alphabet':'aa'},{'extra_keys':['x','x']},{'wrong':1}):
            with self.subTest(value=value), self.assertRaises(InputError): Domain.from_dict(value)

    def test_domain_budgets(self):
        from schema_boundary.domain import Domain
        from schema_boundary.io import Unsupported
        with self.assertRaises(Unsupported): Domain(max_depth=3,max_items=8).resolve_keys({str(i) for i in range(12)})


if __name__ == '__main__': unittest.main()
