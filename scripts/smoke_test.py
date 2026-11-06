"""Start Uvicorn on loopback, check real HTTP responses, and stop it."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).resolve().parents[1],
    )

    def request(path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(
            base + path, data=data, headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=3) as response:
            return response.status, json.load(response)

    try:
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError("Uvicorn exited before startup")
            try:
                check(
                    request("/health") == (200, {"status": "ok"}), "Health check failed"
                )
                break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Uvicorn startup timed out")
                time.sleep(0.1)

        status, account = request(
            "/accounts", {"owner": "Smoke Test", "currency": "USD"}
        )
        check(status == 201, "Account creation failed")
        check(account["balance_cents"] == 0, "Initial balance is not zero")
        check(type(account["balance_cents"]) is int, "Balance is not an integer")
        path = f"/accounts/{account['account_id']}"
        check(request(path) == (200, account), "Account retrieval mismatch")
        check(
            request(path + "/balance")
            == (
                200,
                {
                    "account_id": account["account_id"],
                    "balance_cents": 0,
                    "currency": "USD",
                },
            ),
            "Balance retrieval mismatch",
        )
        for path, payload, expected in [
            ("/accounts/missing", None, 404),
            ("/accounts/missing/balance", None, 404),
            ("/accounts", {"owner": " ", "currency": "USD"}, 422),
        ]:
            try:
                request(path, payload)
            except HTTPError as error:
                check(
                    error.code == expected,
                    f"Expected HTTP {expected}, received {error.code}",
                )
            else:
                raise AssertionError(f"Expected HTTP {expected}")
        with urlopen(base + "/docs", timeout=3) as response:
            check(response.status == 200, "Documentation unavailable")
        check(request("/openapi.json")[0] == 200, "OpenAPI unavailable")
        bad_bodies = [
            ('{"owner":"Name","currency":"USD"}'.encode("utf-16-le"), 422),
            ('{"owner":"Name","currency":"USD"}'.encode("utf-32-be"), 422),
            (b'{"owner":NaN,"currency":"USD"}', 422),
            (b'{"owner":Infinity,"currency":"USD"}', 422),
            (b'{"owner":-Infinity,"currency":"USD"}', 422),
            (b'{"owner":"\\ud800","currency":"USD"}', 422),
            (b'{"owner":"\\nName","currency":"USD"}', 422),
            (b'{"owner":"\xff","currency":"USD"}', 400),
            (b" " * 4097, 413),
        ]
        for body, expected in bad_bodies:
            req = Request(
                base + "/accounts",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urlopen(req, timeout=3):
                    raise RuntimeError("Malformed request unexpectedly succeeded")
            except HTTPError as error:
                check(
                    error.code == expected,
                    f"Regression: expected {expected}, got {error.code}",
                )
                detail = json.load(error)
                check(set(detail) == {"detail"}, "Unexpected validation response")
        req = Request(base + "/health", headers={"Host": "attacker.example"})
        try:
            with urlopen(req, timeout=3):
                raise RuntimeError("Untrusted Host unexpectedly accepted")
        except HTTPError as error:
            check(error.code == 400, "Host validation failed")
        print(
            "PASS: live startup, endpoints, errors, malformed-input regressions, body limit, Host check, docs"
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
