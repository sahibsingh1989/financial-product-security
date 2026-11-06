import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def create_account(client):
    return client.post("/accounts", json={"owner": "Test User", "currency": "USD"})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_account(client):
    response = create_account(client)
    assert response.status_code == 201
    account = response.json()
    assert account == {
        "account_id": account["account_id"],
        "owner": "Test User",
        "currency": "USD",
        "balance_cents": 0,
    }
    assert account["account_id"].startswith("acc_")
    assert response.headers["location"] == f"/accounts/{account['account_id']}"


def test_retrieve_account(client):
    account = create_account(client).json()
    response = client.get(f"/accounts/{account['account_id']}")
    assert response.status_code == 200
    assert response.json() == account


def test_zero_integer_balance(client):
    account = create_account(client).json()
    response = client.get(f"/accounts/{account['account_id']}/balance")
    assert response.status_code == 200
    assert response.json() == {
        "account_id": account["account_id"],
        "balance_cents": 0,
        "currency": "USD",
    }
    assert type(response.json()["balance_cents"]) is int


@pytest.mark.parametrize("suffix", ["", "/balance"])
def test_missing_account(client, suffix):
    response = client.get(f"/accounts/acc_missing{suffix}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Account not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"owner": "Test User"},
        {"currency": "USD"},
        {"owner": "", "currency": "USD"},
        {"owner": "   ", "currency": "USD"},
        {"owner": "A" * 101, "currency": "USD"},
        {"owner": 123, "currency": "USD"},
        {"owner": None, "currency": "USD"},
        {"owner": "Test User", "currency": "EUR"},
        {"owner": "Test User", "currency": "usd"},
        {"owner": "Test User", "currency": "USD", "balance_cents": 100},
        [],
        None,
    ],
)
def test_invalid_input(client, payload):
    assert client.post("/accounts", json=payload).status_code == 422


def test_malformed_json(client):
    response = client.post(
        "/accounts", content="{broken", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_unique_accounts(client):
    accounts = [create_account(client).json() for _ in range(20)]
    assert len({account["account_id"] for account in accounts}) == 20
    for account in accounts:
        assert client.get(f"/accounts/{account['account_id']}").json() == account


def test_trim_owner_and_allow_unicode(client):
    response = client.post(
        "/accounts", json={"owner": "  José 李  ", "currency": "USD"}
    )
    assert response.status_code == 201
    assert response.json()["owner"] == "José 李"


def test_app_instances_do_not_share_accounts(client):
    account_id = create_account(client).json()["account_id"]
    with TestClient(create_app()) as separate_client:
        assert separate_client.get(f"/accounts/{account_id}").status_code == 404
