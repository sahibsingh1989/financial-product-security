# Financial Product Security & Automated Vulnerability Research

Version 0.1.0 — Week 1 educational FastAPI prototype with input-hardening fixes.

Creates simulated USD accounts and retrieves their details and balances. No real
money moves. This API has no authentication or authorization: anyone who can
reach it and knows an account ID can read that account. Use synthetic data and
run locally. It is not production-ready.

## Setup (PowerShell)

Use Python 3.12 or newer. From this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

No environment activation is required. For the exact verified dependency versions,
install `requirements-lock.txt` instead of `requirements-dev.txt`. Python 3.12 is
the locally verified and CI-configured version; newer versions are not yet tested.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-proxy-headers
```

Interactive API documentation: <http://127.0.0.1:8000/docs>
OpenAPI schema: <http://127.0.0.1:8000/openapi.json>
Stop the server with Ctrl+C. Use one worker because storage is process-local.
Reloading or restarting the server discards all accounts.

## Try the API (another PowerShell window)

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
$account = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/accounts -ContentType 'application/json' -Body '{"owner":"Test User","currency":"USD"}'
$account
Invoke-RestMethod "http://127.0.0.1:8000/accounts/$($account.account_id)"
Invoke-RestMethod "http://127.0.0.1:8000/accounts/$($account.account_id)/balance"
```

| Method | Path | Success |
| --- | --- | --- |
| GET | `/health` | 200, `{"status":"ok"}` |
| POST | `/accounts` | 201, full account plus Location header |
| GET | `/accounts/{account_id}` | 200, full account |
| GET | `/accounts/{account_id}/balance` | 200, ID, integer balance, currency |

Account IDs use `acc_` followed by a UUID4 hex string. Accounts start with
`balance_cents: 0`; there are no balance mutation endpoints. Owner names must be
strings containing 1–100 characters after trimming whitespace. Unicode names
are supported except Unicode control (`Cc`), format (`Cf`, including bidi controls),
and surrogate (`Cs`) characters, which are rejected before trimming. Length is
measured in Unicode code points, not displayed graphemes. This is input validation,
not identity verification. Currency must
be exactly `USD`. Missing fields, extra fields (including a supplied balance),
invalid types, malformed JSON, and unsupported currencies return HTTP 422.
Unknown account IDs return HTTP 404 with `{"detail":"Account not found"}`.
Validation responses use only `{"detail":"Invalid request body"}` without input,
field names, or validation contexts. Invalid UTF-8 bytes or a declared non-UTF-8
charset return 400. UTF-16/32 JSON is rejected even when its bytes happen to decode
as UTF-8; JSON parsing uses decoded UTF-8 text without encoding autodetection.
UTF-8 with no charset, `charset=utf-8`, or `charset=utf8` is supported.
UTF-8 BOM-prefixed JSON is rejected with 422. JSON numeric
tokens `NaN`, `Infinity`, and `-Infinity` are rejected with 422. Bodies over 4096
bytes return 413, counted from received bytes even without Content-Length.
Valid JSON plus whitespace totaling exactly 4096 bytes is permitted.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -O scripts/smoke_test.py
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m ruff format --check app tests scripts
.\.venv\Scripts\python.exe -m bandit -r app -q
```

Tests create a fresh application and store per test. They cover all endpoints,
zero integer balances, independent accounts, IDs, missing accounts, malformed
requests, input constraints, Unicode names, and store isolation.
The smoke test starts a temporary local Uvicorn server, checks real HTTP requests,
malformed-input regressions, Host rejection, and documentation, then stops the
server. Its explicit checks also run under Python optimization (`-O`).
The GitHub Actions workflow runs tests, the smoke test, Ruff, and Bandit on Python
3.12/Linux when pushed. Local execution does not establish a successful hosted CI run.

`requirements-dev.txt` describes supported dependency ranges.
`requirements-lock.txt`, when present, records the exact environment used during
verification; install it with `python -m pip install -r requirements-lock.txt`.

## Structure

```text
.github/workflows/tests.yml    GitHub Actions test and static-check workflow
.gitignore                    Local artifact and secret-file exclusions
app/
  __init__.py                 Application package
  main.py                     App factory, routes, error handler, OpenAPI responses
  middleware.py               Body limit, UTF-8 and JSON validation
  models.py                   Request/response models and name validation
  store.py                    Locked in-memory account dictionary
scripts/
  smoke_test.py               Real-server checks (also run under python -O)
tests/
  test_api.py                 Endpoint and input tests
  test_hardening.py           Input-security and store/model regressions
  test_documentation_encoding.py  OpenAPI and request-encoding regressions
requirements.txt
requirements-dev.txt
requirements-lock.txt
pyproject.toml
LICENSE
README.md
SECURITY.md
VERIFICATION.md
```

Request flow: TrustedHostMiddleware checks the Host; BodyLimitMiddleware bounds
and validates the body and encoding; Pydantic validates the account request;
the endpoint calls the store; FastAPI serializes a response model. Validation
errors use a generic response that omits submitted input. OpenAPI documents these
JSON errors, plain-text Host rejection, account 404s, and the creation Location
header. Each `create_app()` call creates
its own store. A lock protects dictionary access within one process; this is not
a transaction or distributed concurrency system. Account models are immutable.
Money uses integer cents throughout.
`create_app(store=...)` accepts an injected AccountStore for tests; this allows
nonzero-balance response verification without adding deposit or transfer APIs.

## Local HTTP boundaries

Allowed Host names are `127.0.0.1`, `localhost`, and `testserver` (test client).
Other hosts return 400. Automatic trailing-slash redirects are disabled:
`/accounts/` returns 404 rather than constructing a redirect from the Host header.
The creation Location header is relative. These controls do not authenticate callers.
See [SECURITY.md](SECURITY.md) for proxy and resource-limit assumptions.

## Limitations and next steps

No persistence, authentication, ownership checks, ledger, transfers, idempotency,
USDC integration, rate limits, or audit logging is implemented. Ruff and Bandit
checks exist today; CodeQL/SARIF scanning and automated findings triage are planned.
Storage is unbounded and disappears on restart; multiple workers have independent
data. UUIDs are identifiers, not authorization credentials. Health reports process
availability only. No performance or security guarantees are claimed.

Week 2: introduce PostgreSQL, migrations, persistent account storage, database
constraints, and integration tests, while preserving this API contract. Later
milestones add ledger accounting, authorization, transaction integrity, and
security automation, Go services, and USDC testnet integration. All of these are
planned, not implemented capabilities. No remote repository is pushed automatically.

## License

MIT; see [LICENSE](LICENSE).
