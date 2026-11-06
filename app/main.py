from fastapi import FastAPI, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from app.middleware import BodyLimitMiddleware
from app.models import Account, AccountBalance, AccountCreate, ErrorResponse
from app.store import AccountStore


def create_app(store: AccountStore | None = None) -> FastAPI:
    application = FastAPI(
        title="Financial Product Security API",
        version="0.1.0",
        description="Educational in-memory prototype. No authentication or authorization.",
        redirect_slashes=False,
        responses={
            400: {
                "model": ErrorResponse,
                "description": "Invalid request encoding (JSON), or untrusted Host (plain text).",
                "content": {
                    "text/plain": {
                        "schema": {"type": "string"},
                        "example": "Invalid host header",
                    }
                },
            },
            413: {
                "model": ErrorResponse,
                "description": "Request body exceeds 4096 bytes.",
                "content": {
                    "application/json": {
                        "example": {"detail": "Request body too large"}
                    }
                },
            },
            422: {
                "model": ErrorResponse,
                "description": "Malformed JSON or invalid input; submitted input is never included.",
                "content": {
                    "application/json": {"example": {"detail": "Invalid request body"}}
                },
            },
        },
    )
    store = store if store is not None else AccountStore()
    application.add_middleware(BodyLimitMiddleware)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
        www_redirect=False,
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request, _error):
        # Never serialize error input, user-controlled field names, or contexts.
        return JSONResponse(status_code=422, content={"detail": "Invalid request body"})

    def find_account(account_id: str) -> Account:
        account = store.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return account

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post(
        "/accounts",
        response_model=Account,
        status_code=status.HTTP_201_CREATED,
        responses={
            201: {
                "description": "Account created with zero balance.",
                "headers": {
                    "Location": {
                        "description": "Relative URL of the created account.",
                        "schema": {
                            "type": "string",
                            "example": "/accounts/acc_0123456789ab4def8123456789abcdef",
                        },
                    }
                },
            }
        },
    )
    def create_account(request: AccountCreate, response: Response) -> Account:
        account = store.create(request)
        response.headers["Location"] = f"/accounts/{account.account_id}"
        return account

    @application.get(
        "/accounts/{account_id}",
        response_model=Account,
        responses={
            404: {
                "model": ErrorResponse,
                "description": "Account not found.",
                "content": {
                    "application/json": {"example": {"detail": "Account not found"}}
                },
            }
        },
    )
    def get_account(account_id: str) -> Account:
        return find_account(account_id)

    @application.get(
        "/accounts/{account_id}/balance",
        response_model=AccountBalance,
        responses={
            404: {
                "model": ErrorResponse,
                "description": "Account not found.",
                "content": {
                    "application/json": {"example": {"detail": "Account not found"}}
                },
            }
        },
    )
    def get_balance(account_id: str) -> AccountBalance:
        account = find_account(account_id)
        return AccountBalance(**account.model_dump(exclude={"owner"}))

    return application


app = create_app()
