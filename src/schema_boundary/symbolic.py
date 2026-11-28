"""Quantifier-free predicates over one explicit finite JSON tree.

Domain constraints are unconditional. Schema predicates never create auxiliary
existential variables: negation and oneOf therefore retain their JSON meaning.
"""
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace
import time
import z3
from .io import Unsupported

NULL, BOOL, INT, STRING, ARRAY, OBJECT = range(6)

class Tree:
    def __init__(self,domain,keys,*,deadline=None):
        self.domain,self.keys=domain,tuple(keys)
        self.deadline=deadline
        if domain.node_count(keys)>3000: raise Unsupported('domain exceeds 3000 symbolic nodes')
        self.ctx=z3.Context()
        self.constraints=[]; self.nodes=0; self.visits=0
        self.root=self._node(domain.max_depth)

    def val(self,x): return z3.BoolVal(x,ctx=self.ctx)
    def AND(self,*xs): return z3.And(*xs) if xs else self.val(True)
    def OR(self,*xs): return z3.Or(*xs) if xs else self.val(False)
    def SUM(self,xs): return z3.Sum(xs) if xs else z3.IntVal(0,ctx=self.ctx)
    def _int(self,name): return z3.Int(name,ctx=self.ctx)
    def _bool(self,name): return z3.Bool(name,ctx=self.ctx)

    def _node(self,depth):
        prefix='n'+str(self.nodes); self.nodes+=1
        n=SimpleNamespace(kind=self._int(prefix+'k'),number=self._int(prefix+'n'),boolean=self._bool(prefix+'b'),
            length=self._int(prefix+'s'),chars=[self._int(prefix+'c'+str(i)) for i in range(self.domain.max_string)],
            count=self._int(prefix+'a'),children=[],present={},properties={})
        d=self.domain
        self.constraints.extend([n.kind>=NULL,n.kind<=(OBJECT if depth else STRING),
            n.number>=d.integer_min,n.number<=d.integer_max,n.length>=0,n.length<=d.max_string,
            n.count>=0,n.count<=(d.max_items if depth else 0)])
        for char in n.chars: self.constraints.extend([char>=0,char<len(d.alphabet)])
        if depth:
            n.children=[self._node(depth-1) for _ in range(d.max_items)]
            for i,key in enumerate(self.keys):
                n.present[key]=self._bool(prefix+'p'+str(i))
                n.properties[key]=self._node(depth-1)
        return n

    def _charge(self,amount=1):
        if self.deadline is not None and time.monotonic()>=self.deadline:
            raise Unsupported('total_deadline')
        self.visits+=amount
        if self.visits>25000: raise Unsupported('predicate and literal compilation exceeds 25000 work units')

    def equals(self,value,node=None):
        self._charge(1+len(value) if isinstance(value,(str,list,dict)) else 1)
        n=self.root if node is None else node
        if value is None: return n.kind==NULL
        if type(value) is bool: return self.AND(n.kind==BOOL,n.boolean==value)
        if type(value) in (int,float) or isinstance(value,Decimal):
            ratio=Fraction(str(value))
            return self.AND(n.kind==INT,n.number==z3.RealVal(f'{ratio.numerator}/{ratio.denominator}',ctx=self.ctx))
        if type(value) is str:
            if len(value)>len(n.chars) or any(c not in self.domain.alphabet for c in value): return self.val(False)
            return self.AND(n.kind==STRING,n.length==len(value),*(n.chars[i]==self.domain.alphabet.index(c) for i,c in enumerate(value)))
        if type(value) is list:
            if len(value)>len(n.children): return self.val(False)
            return self.AND(n.kind==ARRAY,n.count==len(value),*(self.equals(v,n.children[i]) for i,v in enumerate(value)))
        if type(value) is dict:
            if set(value)-set(n.properties): return self.val(False)
            return self.AND(n.kind==OBJECT,*(n.present[k]==(k in value) for k in n.present),
                            *(self.equals(v,n.properties[k]) for k,v in value.items()))
        return self.val(False)

    def compile(self,schema,node=None):
        self._charge()
        n=self.root if node is None else node
        if type(schema) is bool: return self.val(schema)
        predicates=[]
        if 'type' in schema:
            kinds={'null':NULL,'boolean':BOOL,'integer':INT,'number':INT,'string':STRING,'array':ARRAY,'object':OBJECT}
            selected=schema['type'] if isinstance(schema['type'],list) else [schema['type']]
            predicates.append(self.OR(*(n.kind==kinds[t] for t in selected)))
        if 'const' in schema: predicates.append(self.equals(schema['const'],n))
        if 'enum' in schema: predicates.append(self.OR(*(self.equals(v,n) for v in schema['enum'])))
        for keyword in ('minimum','maximum','exclusiveMinimum','exclusiveMaximum'):
            if keyword not in schema: continue
            value=Fraction(str(schema[keyword]))
            bound=z3.RealVal(f'{value.numerator}/{value.denominator}',ctx=self.ctx)
            relation={'minimum':lambda:n.number>=bound,'maximum':lambda:n.number<=bound,
                      'exclusiveMinimum':lambda:n.number>bound,'exclusiveMaximum':lambda:n.number<bound}[keyword]()
            predicates.append(z3.Implies(n.kind==INT,relation))
        if 'multipleOf' in schema:
            value=Fraction(str(schema['multipleOf']))
            predicates.append(z3.Implies(n.kind==INT,(n.number*value.denominator)%value.numerator==0))
        for keyword,relation in (('minLength',lambda b:n.length>=b),('maxLength',lambda b:n.length<=b)):
            if keyword in schema: predicates.append(z3.Implies(n.kind==STRING,relation(int(schema[keyword]))))
        for keyword,relation in (('minItems',lambda b:n.count>=b),('maxItems',lambda b:n.count<=b)):
            if keyword in schema: predicates.append(z3.Implies(n.kind==ARRAY,relation(int(schema[keyword]))))
        if 'items' in schema:
            predicates.append(z3.Implies(n.kind==ARRAY,self.AND(*(z3.Implies(n.count>i,self.compile(schema['items'],child)) for i,child in enumerate(n.children)))))
        obj=[]
        for key in schema.get('required',[]): obj.append(n.present.get(key,self.val(False)))
        properties=schema.get('properties',{})
        for key in n.properties:
            # additionalProperties applies to this schema object only. Do not
            # union the declared properties of neighboring allOf branches.
            child_schema=properties[key] if key in properties else schema.get('additionalProperties',True)
            if child_schema is not True:
                obj.append(z3.Implies(n.present[key],self.compile(child_schema,n.properties[key])))
        count=self.SUM([z3.If(flag,1,0) for flag in n.present.values()])
        if 'minProperties' in schema: obj.append(count>=int(schema['minProperties']))
        if 'maxProperties' in schema: obj.append(count<=int(schema['maxProperties']))
        predicates.append(z3.Implies(n.kind==OBJECT,self.AND(*obj)))
        for keyword in ('allOf','anyOf','oneOf'):
            if keyword not in schema: continue
            children=[self.compile(child,n) for child in schema[keyword]]
            if keyword=='allOf': predicates.append(self.AND(*children))
            elif keyword=='anyOf': predicates.append(self.OR(*children))
            else: predicates.append(self.SUM([z3.If(child,1,0) for child in children])==1)
        if 'not' in schema: predicates.append(z3.Not(self.compile(schema['not'],n)))
        return self.AND(*predicates)

    def decode(self,model,node=None):
        n=self.root if node is None else node
        number=lambda expr:model.eval(expr,model_completion=True).as_long()
        kind=number(n.kind)
        if kind==NULL: return None
        if kind==BOOL: return z3.is_true(model.eval(n.boolean,model_completion=True))
        if kind==INT: return number(n.number)
        if kind==STRING: return ''.join(self.domain.alphabet[number(char)] for char in n.chars[:number(n.length)])
        if kind==ARRAY: return [self.decode(model,child) for child in n.children[:number(n.count)]]
        if kind==OBJECT: return {k:self.decode(model,v) for k,v in n.properties.items() if z3.is_true(model.eval(n.present[k],model_completion=True))}
        raise ValueError('invalid symbolic kind')
