# Schema Boundary: bounded compatibility witnesses

## Product

Find an actual JSON instance accepted by a source schema and rejected by a target schema. Typical use: source=old tool-input contract, target=new; response-consumer checks often require the opposite direction. No universal compatibility claim, random-testing guarantee, full OpenAPI parser, remote references, hosted service or LLM call.

Alternative routes considered: full JSON Schema inclusion (too broad for a credible first release), random instance generation (does not establish bounded absence), and bounded SMT (selected). IBM/jsonsubschema already studies inclusion; OpenAPITools/openapi-diff and getsentry/json-schema-diff already provide change reports. This project does not claim invention or superior market performance.

## Finite domain

An explicit Domain dataclass controls: max_depth=2 (number of nested containers, depth0 only scalars), max_items=2, max_string=8 Unicode codepoints, alphabet='abcdefghijklmnopqrstuvwxyz0123456789_-', integer_min=-16, integer_max=16, extra_keys=('__extra__',). Object keys are the sorted union of properties/required/const-object keys from both schemas plus extra_keys, recursively collected, at most 12. All objects in the domain use subsets of this same key set. Only integer-valued JSON numbers occur in the domain. Decimal schema bounds/multipleOf remain exact. This intentionally excludes nonintegral instances, longer strings, other characters, deeper/larger containers, and keys outside the printed set. None of these exclusions may be hidden behind an unqualified 'compatible'. Empty strings/arrays/objects and all scalar types are included where depth permits.

The symbolic AST assigns each potential node a kind (null/bool/int/string/array/object), bool/int scalar, bounded char-index vector with active length, bounded child arrays, and presence flags plus children for each allowed key. All auxiliary domain constraints are unconditional (not hidden inside old/new predicates), so negation/oneOf does not accidentally negate existential helper constraints. For inactive children, domain constraints remain satisfiable and impose no conditions on active parents. Compile predicates are pure Boolean expressions over this fixed tree.

Limits: input 1MiB/file, total JSON depth32 and 4000 nodes, 128 Unicode alphabet codepoints, domain max_depth3/max_items8/max_string64, integer endpoints absolute <=10^12, <=3000 symbolic nodes, <=25000 shared predicate/literal compilation work units. Reject before expanding over-budget trees. Solver timeout 5000ms per check and rlimit 2000000 per check by default; local Context and solver parameters only, no global Z3 settings. A single monotonic total deadline covers the comparison pipeline after source/target/domain inputs are loaded: domain construction, normalization, validation, compilation, both solver checks, witness verification, evidence serialization and independent replay; each solver check receives only the remaining budget. CLI file reading and initial JSON parsing occur before this deadline.

## Schema subset

Draft 2020-12 only. Boolean schemas. type (incl type arrays), const/enum (full JSON literals), minimum/maximum/exclusiveMinimum/exclusiveMaximum/multipleOf; minLength/maxLength; arrays items/minItems/maxItems; objects properties/required/additionalProperties (bool or schema)/minProperties/maxProperties; allOf/anyOf/oneOf/not. Annotations title/description/$comment/default/examples/deprecated/readOnly/writeOnly may be ignored explicitly. '$schema' must equal https://json-schema.org/draft/2020-12/schema with optional #. Any unsupported keyword (including format, pattern, $ref, $defs, prefixItems, uniqueItems, unevaluated*, custom extensions) anywhere in schema positions returns unknown. Annotation values and const/enum literal keys are data, not schema keywords.

Strict UTF8 JSON: reject duplicate keys, nonfinite numbers, lone surrogates, excessive numbers/depth/nodes. Parse decimals as Decimal; convert bounds to Fraction and exact Z3 rationals. Generated instances contain only null/bool/int/str/list/dict and are serialized with standard json then parsed again before independent validation. JSON numeric equality differs from bool equality. additionalProperties is local to each schema object; no merging properties across allOf. Keywords do not imply type.

## Results and independent verification

API compare(source, target, domain=None, timeout_ms=5000, rlimit=2000000) returns schema_version=1, status, reason, direction='source-minus-target', domain (including resolved keys), limits, hashes (canonical schema SHA256), engines (versions), witness or null, verification, failures, stats. Canonical decimal serialization preserves number value, sorted keys; no local paths or schema annotation contents in reports. For a null counterexample, status distinguishes null witness from absent witness.

First check domain AND source: UNSAT -> empty-source (vacuous only within domain, not compatibility); UNKNOWN -> unknown. Then add NOT target: UNSAT -> bounded-compatible only after independent replay; UNKNOWN -> unknown. Replay evidence contains only the finite domain and annotation-free normalized source/target schemas plus format, encoder and canonical digest. Annotations are stripped only at schema positions; keys and values inside const/enum literals are preserved as data. The replay validates those inputs, rebuilds the domain and both predicates with a fresh Tree/Z3 context under the same total deadline, and solves domain_constraints AND source AND NOT target. It never parses serialized assertions or SMT text. SAT -> decode and JSON roundtrip; independent Draft202012Validator must accept source and reject target. Also revalidate the witness belongs to the printed domain independently of the SMT model. If either check disagrees or raises -> unknown, never a confirmed counterexample. Counterexamples include target JSON Pointer instance/schema paths and validator keyword. Not guaranteed unique, globally minimal or stable between solver versions.

CLI: schema-boundary compare SOURCE TARGET [--domain JSON] [--output DIR] [--accept-bounded] [--timeout-ms N] [--rlimit N]. Output dir is new-only and cannot already exist, no overwrites, no inferred remote behavior. stdout JSON; exit1 counterexample, exit3 bounded-compatible (or0 with explicit --accept-bounded), exit4 empty-source, exit2 unknown/error. Input misuse emits structured error. Output files: report.json, report.html, and witness.json only for validated counterexample (including JSON null). Reports are UTF8 and self-contained HTML without scripts or outside assets. All text escaped, obvious amber bounded/unknown states, concrete witness and paths, full domain visible. No green checkmark for bounded results.

## Architecture/files

src/schema_boundary/io.py: strict loads/read/schema canonical hashes; InputError, Unsupported.
schema.py: independent metaschema validation plus schema-position whitelist scan, schema-position annotation stripping, and key collection.
domain.py: Domain immutable config validation, resolved-key cardinality/budget, independent contains(instance).
symbolic.py: symbolic tree, exact literal equality, compile(schema), decode(model).
proof.py: self-describing UNSAT evidence and independent fresh-context replay from validated inputs.
engine.py: solver protocol and independent validator gate.
report.py: pure HTML renderer.
cli.py, __main__.py, __init__.py: public CLI/version.
Tests separated by parser, predicates, end-to-end engine, package/CLI. Public self-contained demonstration and known-different/relaxed/unsupported schemas. Dependencies z3-solver (MIT), jsonschema (MIT), licensed transitives documented. Original code MIT. Python>=3.10. No user data samples.

## Quality gates

Tests first, exhaustive independent enumeration over tiny domains for each supported keyword and mixed schemas (both SAT and UNSAT), numerical/boolean/Unicode cases, bounded blind-spot demonstration with a counterexample just outside the domain, true solver resource UNKNOWN, fabricated-witness/disabled-keyword/negation mutation controls, clean installed wheel CLI and browser screenshots. Independent review if agent is available; otherwise explicitly report missing independence and leave coordination verification pending. No self-declared world-leading status.

Publish only via the user's unified coordinator. No remote URL will be described as already published before a receipt. This project is a bounded-checker alpha even if all tests pass.
