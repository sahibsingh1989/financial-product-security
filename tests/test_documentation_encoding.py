import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize(
    "encoding", ["utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"]
)
@pytest.mark.parametrize(
    "content_type", ["application/json", "application/problem+json"]
)
def test_non_utf8_json_is_rejected(client, encoding, content_type):
    body = json.dumps({"owner": "Name", "currency": "USD"}).encode(encoding)
    response = client.post(
        "/accounts", content=body, headers={"Content-Type": content_type}
    )
    assert response.status_code in {400, 422}
    assert response.json() in [
        {"detail": "Invalid UTF-8 request body"},
        {"detail": "Invalid request body"},
    ]


@pytest.mark.parametrize("charset", ["utf-16", "utf-32", "iso-8859-1", "unknown"])
def test_non_utf8_declared_charset_is_rejected(client, charset):
    response = client.post(
        "/accounts",
        content=b'{"owner":"Name","currency":"USD"}',
        headers={"Content-Type": f"application/json; charset={charset}"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid UTF-8 request body"}


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        'application/json; charset="UTF-8"',
        "application/json; charset=utf8",
    ],
)
def test_utf8_unicode_json_is_accepted(client, content_type):
    body = json.dumps(
        {"owner": "José 李", "currency": "USD"}, ensure_ascii=False
    ).encode("utf-8")
    response = client.post(
        "/accounts", content=body, headers={"Content-Type": content_type}
    )
    assert response.status_code == 201
    assert response.json()["owner"] == "José 李"


def test_openapi_error_contract(client):
    schema = client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        for operation in operations.values():
            responses = operation["responses"]
            for code in ["400", "413", "422"]:
                error_schema = responses[code]["content"]["application/json"]["schema"]
                assert error_schema == {"$ref": "#/components/schemas/ErrorResponse"}
            assert responses["400"]["content"]["text/plain"]["schema"] == {
                "type": "string"
            }
            if "{account_id}" in path:
                assert responses["404"]["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorResponse",
                }
    assert schema["components"]["schemas"]["ErrorResponse"]["properties"] == {
        "detail": {"type": "string", "title": "Detail"},
    }
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_openapi_creation_location(client):
    response = client.post("/accounts", json={"owner": "Name", "currency": "USD"})
    assert response.headers["location"] == "/accounts/" + response.json()["account_id"]
    schema = client.get("/openapi.json").json()
    created = schema["paths"]["/accounts"]["post"]["responses"]["201"]
    assert created["headers"]["Location"]["schema"]["type"] == "string"
    assert created["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Account"
    }


def test_utf8_bom_json_is_rejected(client):
    response = client.post(
        "/accounts",
        content=b'\xef\xbb\xbf{"owner":"Name","currency":"USD"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request body"}
