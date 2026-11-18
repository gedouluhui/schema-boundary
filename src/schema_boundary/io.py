"""Strict bounded JSON input; exact decimal schema numbers."""
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

MAX_BYTES = 1048576

class InputError(ValueError):
    pass

class Unsupported(ValueError):
    pass


def preflight(value):
    stack, count = [(value,0)], 0
    while stack:
        item, depth = stack.pop(); count += 1
        if count > 4000 or depth > 32:
            raise InputError('JSON exceeds 4000 nodes or depth 32')
        if type(item) is dict:
            for key, child in item.items():
                if not isinstance(key,str): raise InputError('JSON object keys must be strings')
                stack.append((key,depth+1)); stack.append((child,depth+1))
        elif type(item) is list:
            stack.extend((x,depth+1) for x in item)
        elif type(item) is str:
            try: item.encode('utf8')
            except UnicodeError as exc: raise InputError('invalid Unicode scalar in JSON') from exc
        elif item is None or type(item) is bool:
            pass
        elif type(item) is int:
            if item.bit_length() > 1024: raise InputError('numeric magnitude exceeds 1024 bits')
        elif isinstance(item,Decimal):
            if not item.is_finite() or abs(item.as_tuple().exponent)>300 or len(item.as_tuple().digits)>300:
                raise InputError('nonfinite or excessive decimal')
        elif type(item) is float:
            if not math.isfinite(item): raise InputError('nonfinite number')
        else: raise InputError('non-JSON value')


def _pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result: raise InputError('duplicate JSON key: '+repr(key))
        result[key] = value
    return result


def _bad_constant(text):
    raise InputError('non-standard JSON constant: '+text)


def loads(text):
    try:
        raw = text if isinstance(text,bytes) else text.encode('utf8')
        if len(raw)>MAX_BYTES: raise InputError('JSON exceeds 1 MiB')
        value = json.loads(raw.decode('utf8'), parse_float=Decimal, parse_constant=_bad_constant, object_pairs_hook=_pairs)
        preflight(value)
        return value
    except (UnicodeError,RecursionError,json.JSONDecodeError) as exc:
        raise InputError('invalid UTF8 JSON or excessive nesting') from exc


def read_json(path):
    try:
        with Path(path).open('rb') as stream: return loads(stream.read(MAX_BYTES+1))
    except OSError as exc: raise InputError('cannot read JSON input') from exc


def canonical(value):
    """Deterministic JSON text; preserves Decimal numbers, never stringifies them."""
    if isinstance(value,Decimal): return str(value)
    if isinstance(value,dict):
        return '{'+','.join(json.dumps(k,ensure_ascii=True)+':'+canonical(value[k]) for k in sorted(value))+'}'
    if isinstance(value,list): return '['+','.join(canonical(v) for v in value)+']'
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',',':'))


def integral_decimals(value):
    """JSON Schema integers are mathematical integers, including the lexeme 1.0."""
    if isinstance(value,Decimal) and value==value.to_integral_value(): return int(value)
    if isinstance(value,dict): return {k:integral_decimals(v) for k,v in value.items()}
    if isinstance(value,list): return [integral_decimals(v) for v in value]
    return value


def normalize(value):
    preflight(value)
    return integral_decimals(loads(canonical(value)))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode('utf8')).hexdigest()
