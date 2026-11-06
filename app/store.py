from threading import Lock
from uuid import uuid4

from app.models import Account, AccountCreate


class AccountStore:
    """Process-local storage; restarting the process discards all accounts."""

    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}
        self._lock = Lock()

    def create(self, request: AccountCreate) -> Account:
        with self._lock:
            account_id = f"acc_{uuid4().hex}"
            while account_id in self._accounts:
                account_id = f"acc_{uuid4().hex}"
            account = Account(account_id=account_id, **request.model_dump())
            self._accounts[account_id] = account
            return account

    def get(self, account_id: str) -> Account | None:
        with self._lock:
            return self._accounts.get(account_id)
