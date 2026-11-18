"""Exhaustive finite-domain checks against independent jsonschema semantics."""
from decimal import Decimal
import importlib.util
import itertools
import unittest
import z3
from jsonschema import Draft202012Validator
from schema_boundary.domain import Domain


def values(domain, keys, depth=None):
    depth = domain.max_depth if depth is None else depth
    scalars = [None,False,True,*range(domain.integer_min,domain.integer_max+1)]
    for n in range(domain.max_string+1):
        scalars += [''.join(v) for v in itertools.product(domain.alphabet,repeat=n)]
    yield from scalars
    if depth:
        children = list(values(domain,keys,depth-1))
        for n in range(domain.max_items+1):
            for group in itertools.product(children,repeat=n): yield list(group)
        for count in range(len(keys)+1):
            for present in itertools.combinations(keys,count):
                for assigned in itertools.product(children,repeat=count): yield dict(zip(present,assigned))

SCHEMAS = [True,False,{}, {'type':'integer'}, {'type':['null','object']},
    {'minimum':Decimal('0.5')}, {'maximum':0}, {'exclusiveMinimum':-1}, {'exclusiveMaximum':1},
    {'multipleOf':Decimal('0.5')},{'multipleOf':2}, {'enum':[True,1,'a']},{'const':False},
    {'const':{'x':1}},{'const':[True]},{'minLength':1},{'maxLength':0},
    {'items':{'type':'integer'}},{'items':False},{'minItems':1},{'maxItems':0},
    {'properties':{'x':{'type':'integer'}}},{'required':['x']}, {'additionalProperties':False},
    {'properties':{'x':True},'additionalProperties':{'type':'string'}},
    {'minProperties':1},{'maxProperties':0},
    {'anyOf':[{'type':'integer'},{'const':None}]},
    {'oneOf':[{'type':'integer'},{'minimum':0}]},
    {'not':{'required':['x']}},
    {'allOf':[{'properties':{'x':True},'additionalProperties':False},{'required':['x']}]},
    {'allOf':[{'properties':{'x':True}}, {'additionalProperties':False}]},
]


class SymbolicTests(unittest.TestCase):
    def test_implementation_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('schema_boundary.symbolic'))

    def test_exhaustive_predicates_against_independent_validator(self):
        from schema_boundary.symbolic import Tree
        d = Domain(max_depth=1,max_items=1,max_string=1,alphabet='a',integer_min=-1,integer_max=1,extra_keys=())
        keys = ('x',)
        tree = Tree(d,keys)
        predicates = [tree.compile(schema) for schema in SCHEMAS]
        references = [Draft202012Validator(schema) for schema in SCHEMAS]
        solver = z3.Solver(ctx=tree.ctx); solver.add(*tree.constraints)
        checked = 0
        for value in values(d,keys):
            solver.push(); solver.add(tree.equals(value))
            self.assertEqual(solver.check(),z3.sat, 'domain member unrepresentable: '+repr(value))
            model = solver.model()
            self.assertEqual(tree.decode(model),value)
            for schema,predicate,validator in zip(SCHEMAS,predicates,references):
                with self.subTest(schema=schema,value=value):
                    actual = z3.is_true(model.eval(predicate,model_completion=True))
                    self.assertIs(actual,validator.is_valid(value))
                checked += 1
            solver.pop()
        self.assertGreater(checked,700)

    def test_unicode_scalar_length_and_literal(self):
        from schema_boundary.symbolic import Tree
        d = Domain(max_depth=0,max_string=2,alphabet='中\U0001F600',extra_keys=())
        tree = Tree(d,())
        solver=z3.Solver(ctx=tree.ctx); solver.add(*tree.constraints,tree.equals('\U0001F600'))
        self.assertEqual(solver.check(),z3.sat)
        self.assertEqual(tree.decode(solver.model()),'\U0001F600')
        self.assertTrue(z3.is_true(solver.model().eval(tree.compile({'minLength':1,'maxLength':1}))))

    def test_literal_expansion_debits_shared_work_budget(self):
        from schema_boundary.symbolic import Tree
        from schema_boundary.io import Unsupported
        tree=Tree(Domain(max_depth=0),())
        tree.visits=24999
        with self.assertRaises(Unsupported): tree.compile({'enum':[1,2]})

    def test_bool_and_integer_distinct(self):
        from schema_boundary.symbolic import Tree
        tree=Tree(Domain(max_depth=0),())
        solver=z3.Solver(ctx=tree.ctx); solver.add(*tree.constraints,tree.equals(True),tree.compile({'const':1}))
        self.assertEqual(solver.check(),z3.unsat)


if __name__=='__main__': unittest.main()
