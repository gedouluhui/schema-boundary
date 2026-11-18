"""Reject unsupported schema positions before any reference resolution."""
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from .io import InputError, Unsupported, preflight, integral_decimals

ANNOTATIONS = {'title','description','$comment','default','examples','deprecated','readOnly','writeOnly'}
SUPPORTED = ANNOTATIONS | {'$schema','type','const','enum','minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf',
    'minLength','maxLength','minItems','maxItems','items','properties','required','additionalProperties','minProperties','maxProperties',
    'allOf','anyOf','oneOf','not'}


def validate_schema(schema):
    preflight(schema)
    schema = integral_decimals(schema)
    keys = set()
    def literal(value):
        if isinstance(value,dict):
            keys.update(value)
            for child in value.values(): literal(child)
        elif isinstance(value,list):
            for child in value: literal(child)
    def walk(s,path):
        if type(s) is bool: return
        if type(s) is not dict: raise InputError('schema at '+path+' must be an object or boolean')
        unknown = set(s)-SUPPORTED
        if unknown: raise Unsupported('unsupported keyword at '+path+': '+','.join(sorted(unknown)))
        if '$schema' in s and s['$schema'] not in ('https://json-schema.org/draft/2020-12/schema','https://json-schema.org/draft/2020-12/schema#'):
            raise Unsupported('only Draft 2020-12 is supported')
        for keyword in ('allOf','anyOf','oneOf'):
            if keyword in s:
                if not isinstance(s[keyword],list): raise InputError(keyword+' requires an array')
                for i,child in enumerate(s[keyword]): walk(child,path+'/'+keyword+'/'+str(i))
        for keyword in ('not','items','additionalProperties'):
            if keyword in s: walk(s[keyword],path+'/'+keyword)
        if 'properties' in s:
            if not isinstance(s['properties'],dict): raise InputError('properties requires an object')
            keys.update(s['properties'])
            for key,child in s['properties'].items(): walk(child,path+'/properties/'+key)
        if 'required' in s:
            if not isinstance(s['required'],list) or any(type(k) is not str for k in s['required']): raise InputError('required must contain strings')
            keys.update(s['required'])
        if 'const' in s: literal(s['const'])
        if 'enum' in s: literal(s['enum'])
    walk(schema,'#')
    try: Draft202012Validator.check_schema(schema)
    except (SchemaError,TypeError,ValueError) as exc:
        path='/'.join(str(p).replace('~','~0').replace('/','~1') for p in getattr(exc,'path',[]))
        raise InputError('invalid Draft 2020-12 schema at /'+path) from exc
    return keys
