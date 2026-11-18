# Verification record — v0.1.0 candidate

Observed on 2026-11-18, Windows / Python 3.12.3, Z3 4.16.0, jsonschema 4.26.0. This record covers a bounded checker candidate, not global schema conformance, real production adoption or world-leading performance. No hosted CI or release is claimed.

## Actual checks

- Maintainer test suite: 33 tests passed, no skips. The predicate test independently enumerates a small JSON domain and compares the symbolic expression against jsonschema for each of 32 schemas; an additional 9-by-9 source/target comparison checks SAT/UNSAT/vacuity decisions against enumerated values. These are explicit finite domains, not exhaustive testing of arbitrary schemas.
- Official JSON-Schema-Test-Suite revision `e2a68a15cd490750fd6b95e604e4054d7d978d1f`: 21 selected keyword files, 609 individual fixtures considered, **425 passed, 184 skipped**. Of the skips, 94 belong to other dialects, 32 contain fractional instance numbers, 7 exceed configured instance-domain caps, and 51 use unsupported keywords. Every skip is named in the generated JSON; none is counted as passing. Source corpus is fetched separately, not bundled.
- Official adapter negative controls: forcing every compiled predicate to true and then false both triggered the specific official-answer disagreement assertion, and neither wrote a passing report. This calibrates those two faults; it does not prove the adapter flawless.
- Six deliberately broken implementations in temporary source copies were caught by their named failing assertions: missing required checks, open additional properties, oneOf weakened to anyOf, exclusive minimum substituted, disabled independent source/domain validation, and ignored unsupported keywords. Original source fingerprints remained unchanged.
- Real solver `rlimit=1` reaches unknown. A counterexample immediately outside the narrower integer domain demonstrates why bounded-compatible cannot be advertised as universal compatibility.
- Headless Edge 157.0.4341.46: 16 browser checks passed, including actual witness/independent result labels, keyboard details, 1280/768/360px document bounds, all non-counterexample status displays, malicious text escaping, no external requests and no page exceptions. Desktop and mobile-width screenshots were opened for visual review. This is not physical-mobile or screen-reader certification.

Reproduction commands are in README. Detailed locally generated evidence is written under ignored `artifacts/`; it is not automatically uploaded with potentially private data.

## Independent review and fixes

The first independent core review found three real defects. The maintainer reproduced them with failing regression tests before fixing:

1. Enum/literal expansion was not debited against the compilation budget. Predicates and literals now share a 25,000-work-unit limit (including string/container lengths). A 618-byte nested enum schema over an 1,885-node domain now reaches the explicit work-budget unknown result; the maintainer measured 5.318 seconds end-to-end on this machine. This is not a one-millisecond wall-time guarantee just because a solver timeout was set to one millisecond.
2. Decimal parsing caused the native meta-validator to reject integer-semantic schema lexemes such as `minLength: 0.0`. Exact integral Decimals are now normalized to int, without a float roundtrip. Fractional constraints retain rational semantics.
3. Native validator error text could echo annotation values from not/oneOf. Reports now emit keyword-plus-pointer diagnostics instead; invalid-meta-schema errors likewise avoid raw value dumps. Property names and witnesses may still be sensitive.

A separate scoped re-review marked all three addressed, checked regression behavior and reported no blocking issue in the change scope. It is not a full formal security audit. A separate attempt to review the verification tools failed with a provider 429 limit before returning a conclusion; no independent-tool-review approval is claimed. The maintainer instead ran the explicit negative controls above.

## Synthetic timing observations

`tools/benchmark.py` measured three repeats per scenario using local `time.perf_counter`, including normalization and compilation. Synthetic breaking-tool case: 0.022–0.034 s; relaxed-tool case: 0.018–0.021 s; a single-integer symbolic range 0..10^12 with its upper boundary removed: 0.011–0.014 s. No external implementation was timed, no RSS/native-memory measurement was made, and these simple cases do not predict general schema performance.

## Installation and release state

The wheel and source distribution built successfully. A new venv installed the actual wheel, imported it from site-packages and ran under `python -I` outside the source tree. Observed counterexample/strict-bounded/opted-in-bounded/unsupported/empty-source exits were 1/3/0/2/4. The written witness was separately read and checked with native jsonschema against the original source/target; existing-output rejection preserved the first case. Wheel Python modules matched reviewed source bytes. The source archive excluded the venv, local artifacts and internal plan. The prepared GitHub Actions matrix is configuration, not evidence that hosted jobs have run.

## Remaining limitations

Only integer-valued instances, explicit string alphabets, finite keys and bounded depth/length. Unsupported schema keywords are unknown. No remote references, formal proof certificate, complete independent proof of UNSAT, adversarial filesystem guarantees, arbitrary-schema performance, Linux/macOS local execution, browser-engine coverage beyond Edge, external user testing or popularity evidence. Dependency versions outside the recorded environment require their own CI. Scope and uncertainty remain visible even when all current checks pass.
