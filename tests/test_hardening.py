import json
import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.middleware import MAX_BODY_BYTES
from app.models import Account, AccountBalance, AccountCreate
from app.store import AccountStore


@pytest.fixture
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("field", ["owner", "currency", "private-key"])
def test_nonfinite_json(client, token, field):
    raw = '{"owner":"Private Name","currency":"USD","' + field + '":' + token + "}"
    response = client.post(
        "/accounts", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request body"}


@pytest.mark.parametrize(
    "character",
    [
        "\x00",
        "\t",
        "\n",
        "\r",
        "\x7f",
        "\x85",
        "\u202e",
        "\u200b",
        chr(0xD800),
        chr(0xDFFF),
    ],
)
def test_problematic_owner_characters(client, character):
    raw = json.dumps({"owner": character + "Name", "currency": "USD"})
    response = client.post(
        "/accounts", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request body"}


@pytest.mark.parametrize(
    "raw",
    [
        b'{"owner":"\xff","currency":"USD"}',
        b'{"owner":"\xed\xa0\x80","currency":"USD"}',
    ],
)
def test_invalid_utf8(client, raw):
    response = client.post(
        "/accounts", content=raw, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid UTF-8 request body"}


@pytest.mark.parametrize(
    "payload",
    [
        {"owner": "private customer", "currency": "secret token"},
        {"owner": "valid", "currency": "USD", "secret-field": "sensitive"},
        {"owner": "valid", "currency": "\ud800"},
        {"owner": "valid", "currency": "USD", "\ud800": 1},
    ],
)
def test_errors_do_not_echo_input(client, payload):
    response = client.post(
        "/accounts",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request body"}


@pytest.mark.parametrize(
    "length,expected", [(0, 422), (1, 201), (100, 201), (101, 422)]
)
@pytest.mark.parametrize("character", ["A", "李"])
def test_owner_boundaries(client, length, expected, character):
    name = character * length
    response = client.post("/accounts", json={"owner": name, "currency": "USD"})
    assert response.status_code == expected
    if expected == 201:
        assert response.json()["owner"] == name


def test_trimmed_maximum(client):
    response = client.post(
        "/accounts", json={"owner": "  " + "A" * 100 + "  ", "currency": "USD"}
    )
    assert response.status_code == 201
    assert response.json()["owner"] == "A" * 100


def test_uuid4_and_integer_creation(client):
    for _ in range(10):
        account = client.post(
            "/accounts", json={"owner": "Name", "currency": "USD"}
        ).json()
        assert re.fullmatch(r"acc_[0-9a-f]{32}", account["account_id"])
        identifier = UUID(hex=account["account_id"][4:])
        assert identifier.version == 4
        assert identifier.variant == "specified in RFC 4122"
        assert type(account["balance_cents"]) is int


def test_account_is_immutable():
    store = AccountStore()
    account = store.create(AccountCreate(owner="Name", currency="USD"))
    for field, value in [("owner", "Changed"), ("balance_cents", 999)]:
        with pytest.raises(ValidationError, match="frozen"):
            setattr(account, field, value)
    assert store.get(account.account_id) == account
    assert account.owner == "Name"
    assert account.balance_cents == 0


@pytest.mark.parametrize("model", [Account, AccountBalance])
@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_money_models_reject_coercion(model, value):
    with pytest.raises(ValidationError):
        model(account_id="acc_test", owner="Name", currency="USD", balance_cents=value)


def test_injected_nonzero_balance():
    class SeededStore(AccountStore):
        def get(self, account_id):
            if account_id == "acc_seed":
                return Account(
                    account_id=account_id,
                    owner="Synthetic",
                    currency="USD",
                    balance_cents=12345,
                )
            return None

    with TestClient(create_app(store=SeededStore())) as client:
        for suffix in ["", "/balance"]:
            response = client.get("/accounts/acc_seed" + suffix)
            assert response.status_code == 200
            assert response.json()["balance_cents"] == 12345
            assert type(response.json()["balance_cents"]) is int


@pytest.mark.parametrize("extra,expected", [(0, 201), (1, 413)])
def test_body_size_boundary(client, extra, expected):
    body = b'{"owner":"Name","currency":"USD"}'
    body += b" " * (MAX_BODY_BYTES - len(body) + extra)
    assert (
        client.post(
            "/accounts", content=body, headers={"Content-Type": "application/json"}
        ).status_code
        == expected
    )


def test_streaming_body_limit(client):
    def chunks():
        yield b'{"owner":"'
        yield b"A" * MAX_BODY_BYTES
        yield b'","currency":"USD"}'

    response = client.post(
        "/accounts", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_deeply_nested_json(client):
    raw = "[" * 1500 + "0" + "]" * 1500
    assert (
        client.post(
            "/accounts", content=raw, headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )


def test_host_and_redirects(client):
    response = client.get(
        "/health", headers={"Host": "attacker.example"}, follow_redirects=False
    )
    assert response.status_code == 400
    assert "location" not in response.headers
    response = client.post(
        "/accounts/", json={"owner": "Name", "currency": "USD"}, follow_redirects=False
    )
    assert response.status_code == 404
    assert "location" not in response.headers


@pytest.mark.parametrize("declared_length", [None, b"1"])
def test_asgi_chunk_limit_without_trusting_length(declared_length):
    import asyncio

    from app.middleware import BodyLimitMiddleware

    async def run():
        messages = iter(
            [
                {"type": "http.request", "body": b"A" * 2048, "more_body": True},
                {"type": "http.request", "body": b"B" * 2049, "more_body": False},
            ]
        )
        sent = []

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        async def downstream(scope, receive, send):
            pytest.fail("Oversized body reached application")

        headers = (
            [] if declared_length is None else [(b"content-length", declared_length)]
        )
        await BodyLimitMiddleware(downstream)(
            {"type": "http", "headers": headers}, receive, send
        )
        assert sent[0]["status"] == 413

    asyncio.run(run())
