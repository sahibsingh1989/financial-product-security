# Version 0.1 hardening verification — November 6, 2026

Environment: Windows, Python 3.12, project-local virtual environment.
Exact installed dependencies are recorded in `requirements-lock.txt`.

Executed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -O scripts/smoke_test.py
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m ruff format --check app tests scripts
.\.venv\Scripts\python.exe -m bandit -r app -q
.\.venv\Scripts\python.exe -m pip check
```

Results:

- pytest: **95 passed, 0 failed**, 1.45 seconds reported by pytest.
- One dependency deprecation warning: Starlette's TestClient currently warns
  that its HTTPX integration is deprecated in favor of HTTPX2. Tests pass with
  the locked HTTPX version; review this when updating test dependencies.
- Before changes: independently reproduced HTTP 500 for owner values `NaN`,
  `Infinity`, and an escaped unpaired Unicode surrogate using TestClient with
  server exception propagation disabled.
- After changes: live Uvicorn smoke test passed startup, all four API endpoints,
  missing-account 404s, invalid-owner 422, `/docs`, and `/openapi.json`. NaN,
  Infinity, negative Infinity, escaped surrogate, and newline owner requests
  returned 422; invalid UTF-8 returned 400; oversized body returned 413; an
  untrusted Host returned 400. UTF-16LE and UTF-32BE JSON returned 422.
  Temporary server stopped.
- Smoke test executed under `python -O`; checks do not depend on Python asserts.
- Ruff lint and formatting: passed for all nine Python files.
- Bandit: passed application-source scan with no reported findings.
- Dependency check: no broken requirements found.
- Publication review: enumerated all 19 nonignored candidate files, inspected
  project content, and scanned for common private-key and credential patterns;
  no secrets or private files identified. Confirmed `.env`, private files,
  attachments, keys, environments, and test/lint caches are ignored. Pattern
  checks cannot prove that arbitrary secrets are absent.

Tests and real HTTP checks ran with approved normal local permissions because
the restricted desktop execution environment previously blocked local sockets.
The results do not represent load testing, security certification, persistence,
or production readiness. The new GitHub Actions workflow has not been run on
GitHub; its Python checks were executed locally on Windows, not Linux CI.

Git was initialized locally on `main`. No remote was configured and no code was
pushed. Authentication, authorization, real payments, and database work remain
outside this version's scope.

Regression coverage includes UUID4 encoding/version/variant, strict integer
balances (including injected nonzero balances), frozen account assignment,
owner length 0/1/100/101 for ASCII and Unicode, disallowed character categories,
redacted validation errors, malformed UTF-8, nonstandard numeric tokens, JSON
nesting, body byte boundaries, genuine ASGI chunks without Content-Length and
with an inaccurate declared length, Host rejection, and disabled slash redirects.
Final corrections add OpenAPI error-schema and Location-header checks, UTF-16/32
encoding regressions, declared-charset rejection, accepted UTF-8 Unicode input,
and BOM rejection. OpenAPI documents JSON errors with a `detail` string rather
than FastAPI's default validation-error list, and the plain-text Host error.

Git email privacy: the global Git configuration used a personal address. The
repository-specific address was changed to the ID-based GitHub noreply format
using the authenticated account ID and username. No global Git setting was
changed. Author and committer identities were checked before preparing the
initial commit. No existing commits required rewriting. GitHub web email-privacy
and push-blocking settings were not inspected or changed.

Remaining limitations: the HTTPX TestClient deprecation warning remains; storage
and request counts are unbounded; slow clients and HTTP headers require server
or proxy controls; no authentication, authorization, or persistence exists. See
SECURITY.md for the conservative Unicode rule and future proxy requirements.
