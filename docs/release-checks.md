# Local v1 release checks — 6 November 2026

Scope: one trusted OS user, loopback services, synthetic inputs, private source
repository. Hosted accounts, production operations, compressed audio decoding,
and redistribution of dependency binaries are not this release's scope.

## Reproducible checks

```sh
python -m compileall -q api scripts
python scripts/check_secrets.py --include-build
python scripts/license_inventory.py
# Security tools run in a separate environment, not the application environment:
pip-audit --disable-pip --no-deps -r requirements.lock
bandit -r api scripts -ll
ruff check api scripts --select E9,F63,F7,F82
```

Run the normal database tests only against a dedicated `*_test` database, following
README. They delete test rows. `npm ci`, the frontend build/audit and browser flow
are exercised on a fresh GitHub Actions runner; current PR checks describe the
latest source revision. The live provider is absent from CI.

Actual local results for this continuation:

- Ruff0.17.3's syntax/undefined-name checks passed. Bandit1.9.4 initially flagged
  the static `FOR UPDATE` suffix in `recording()` as a possible SQL injection. The
  ID was already parameter-bound and the suffix depended only on a trusted bool;
  no input-driven SQL injection was found. Selecting two complete constant
  queries now makes that boundary explicit without changing locking behavior.
- The locked Python dependency audit reported no known vulnerabilities; the
  frontend npm audit reported zero across all severities. These are dated advisory
  checks, not a security certification.
- The repository/build secret-pattern scanner reports filenames only. The
  coordinator can additionally supply a known value through `SECRET_SCAN_VALUE`
  without putting it in an argument or reading credentials inside the scanner.
  Private ignored runtime files, Git history, binary/OCR content and unknown
  credential formats are outside this bounded scan.
- The license inventory checks all25 installed Python versions against the lock
  and records125 npm lock entries, including development/optional platforms.
  Its metadata and notice paths are in [licenses.json](licenses.json).

## Dependency and asset attribution

Original application code has no owner-selected public redistribution license.
This review does not choose one. Dependencies retain their own licenses/notices;
the inventory records metadata rather than granting legal clearance.

Principal components: FastAPI (MIT), Starlette (BSD), Pydantic (MIT), Psycopg
(LGPL), Redis Python client (MIT), React/React DOM (MIT), Lucide (ISC), Vite/Rollup
(MIT), TypeScript/Playwright (Apache-2.0). Certifi declares MPL2.0; the two axe
accessibility test packages declare MPL2.0; caniuse-lite data declares CC-BY4.0.
The inventory preserves exact declarations, including classifier-only metadata.
Installed package directories retain copyright/license files; no dependency
source was modified or relicensed. Packaging a distributable binary requires its
own notice/source handling review. PostgreSQL/Redis service images have separate
upstream terms and are not covered by the Python/npm metadata inventory.

The sample and independent evaluation speech are locally synthesized using macOS
`say`/`afconvert`; their authored manifests record source/hash provenance. Screenshots
show synthetic data. No production call, external artwork or hosted recording is
bundled. Database/Redis official images run their service processes without root
after initialization; this application does not introduce an app container.

## Acceptance boundary

The fixture/browser workflow, actual initial Gemini development workflow and
independent frozen-gate evaluation have separate records. See
[live validation](live-validation.md) and [independent evaluation](independent-evaluation.json).
HTTP503 prevents new quality scores; a failed or unattempted recording is not a
pass. Service failures do not trigger automatic retry, alternate models or billing
changes. The current model restriction also leaves a second provider unverified.
No production load, diarization, hosted isolation or secure-erasure claim is made.
