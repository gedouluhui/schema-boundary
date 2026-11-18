# Third-party notices

Original Schema Boundary code and synthetic examples are MIT licensed. Dependencies are installed separately, not vendored into our wheel.

| Package | Observed version in development | Declared license |
|---|---|---|
| z3-solver | 4.16.0.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| attrs | 26.1.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| referencing | 0.37.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |

Versions above were read from installed package metadata. Follow each dependency's bundled license; the project's dependency ranges permit later compatible releases whose resolved metadata should be checked again.

The optional [JSON-Schema-Test-Suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite) corpus is MIT licensed (copyright Julian Berman). It is cloned separately under ignored local artifacts, not redistributed in this wheel or source distribution. Its revision and selected-case coverage are recorded in verification output. Normative JSON Schema specifications are referenced, not copied into the product source.

Optional Playwright browser verification is a development tool only (Apache-2.0), not a runtime or installed product dependency. No third-party images, web fonts, model weights or datasets are included.
