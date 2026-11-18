"""Explicit finite JSON universe; membership is independent of the SMT encoder."""
from dataclasses import dataclass, asdict, fields
from .io import InputError, Unsupported

@dataclass(frozen=True)
class Domain:
    max_depth: int = 2
    max_items: int = 2
    max_string: int = 8
    alphabet: str = 'abcdefghijklmnopqrstuvwxyz0123456789_-'
    integer_min: int = -16
    integer_max: int = 16
    extra_keys: tuple[str,...] = ('__extra__',)

    def __post_init__(self):
        for name,limit in (('max_depth',3),('max_items',8),('max_string',64)):
            value = getattr(self,name)
            if type(value) is not int or not 0<=value<=limit: raise InputError(f'{name} must be an integer in [0,{limit}]')
        for number in (self.integer_min,self.integer_max):
            if type(number) is not int or abs(number)>10**12: raise InputError('integer endpoints must be integers within +/-10^12')
        if self.integer_min>self.integer_max: raise InputError('integer_min exceeds integer_max')
        if type(self.alphabet) is not str or not 1<=len(self.alphabet)<=128 or len(set(self.alphabet))!=len(self.alphabet):
            raise InputError('alphabet must contain 1..128 unique Unicode codepoints')
        if not isinstance(self.extra_keys,(tuple,list)) or any(type(k) is not str for k in self.extra_keys) or len(set(self.extra_keys))!=len(self.extra_keys):
            raise InputError('extra_keys must be unique strings')
        try:
            self.alphabet.encode('utf8')
            for key in self.extra_keys: key.encode('utf8')
        except UnicodeError as exc: raise InputError('invalid Unicode domain') from exc
        object.__setattr__(self,'extra_keys',tuple(self.extra_keys))

    @classmethod
    def from_dict(cls, obj):
        if type(obj) is not dict or set(obj)-{f.name for f in fields(cls)}: raise InputError('unknown or invalid domain fields')
        return cls(**obj)

    def resolve_keys(self, declared):
        keys = tuple(sorted(set(declared)|set(self.extra_keys)))
        if len(keys)>12: raise Unsupported('domain exceeds 12 object keys; reduce schemas or extra_keys')
        if self.node_count(keys)>3000: raise Unsupported('domain expansion exceeds 3000 symbolic nodes')
        return keys

    def node_count(self, keys):
        branch = len(keys)+self.max_items
        return sum(branch**i for i in range(self.max_depth+1))

    def to_dict(self, keys):
        return {**asdict(self),'extra_keys':list(self.extra_keys),'object_keys':list(keys),
                'numbers':'integers only','symbolic_nodes':self.node_count(keys)}

    def contains(self,value,keys):
        def inside(item,depth):
            if item is None or type(item) is bool: return True
            if type(item) is int: return self.integer_min<=item<=self.integer_max
            if type(item) is str: return len(item)<=self.max_string and all(c in self.alphabet for c in item)
            if depth==0: return False
            if type(item) is list: return len(item)<=self.max_items and all(inside(v,depth-1) for v in item)
            if type(item) is dict: return all(k in keys and inside(v,depth-1) for k,v in item.items())
            return False
        return inside(value,self.max_depth)
