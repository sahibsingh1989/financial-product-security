# Security scope and local development boundaries

This Week 1 prototype is for synthetic accounts on a local machine. It has no
authentication or authorization, no financial operations, and no durable store.
Input hardening does not make it a secure financial platform.

- Bind Uvicorn to loopback, use a single worker, and disable proxy headers for
  direct local use as shown in the README.
- Host checking accepts only loopback names and `testserver`. Trailing-slash
  redirects are disabled and account Location headers are relative. Host validation
  is not an access-control mechanism and does not prevent all browser-origin attacks.
- A future proxy deployment must configure exact public allowed hosts, remove
  `testserver`, reject unknown hosts at the edge, and trust forwarded headers only
  from explicitly configured proxy IPs. Do not trust arbitrary forwarded hosts.
  TLS, authentication, authorization, and a deployment review remain future work.
- Bodies are bounded to 4096 bytes before JSON validation, counting received bytes
  rather than trusting Content-Length. UTF-8 is required; declared charsets must
  be `utf-8` or `utf8` when supplied. JSON is parsed from decoded UTF-8 text, so
  Python's byte-based UTF-16/32 autodetection cannot bypass this policy. Invalid
  UTF-8 or unsupported charset declarations return 400; UTF-16/32 bytes that are
  also valid UTF-8 but invalid JSON text return 422. UTF-8 BOM-prefixed JSON is
  rejected with 422. This application-level
  limit does not bound HTTP headers, the server's individual incoming buffers,
  slow uploads, concurrent requests, or the total in-memory account count. Proxy
  timeouts, rate limits, and request limits would be required for exposure.
- Owner names reject Unicode categories Cc, Cf, and Cs before whitespace trimming.
  The conservative Cf rule also excludes some legitimate names containing joiners.
  Names are not verified identities; Unicode confusables and normalization are
  not addressed. Request validation responses omit all submitted values and keys.
- The frozen account model prevents ordinary field assignment; it is not a
  security boundary against code executing inside the Python process.
- Do not submit actual customer data, real account details, credentials, or keys.
  `.gitignore` excludes common local secrets and artifacts but cannot detect all
  secrets or protect already tracked files. Review the publication set before
  every push. GitHub publication remains a separate approval step.

GitHub Actions provides tests and basic static checks only. There is no implemented
CodeQL/SARIF triage, financial security certification, or dependency vulnerability
audit. Report only reproduced behavior; planned features are described in README.
