import unicodedata
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    StrictInt,
    StringConstraints,
)


def validate_owner_characters(value: object) -> object:
    # Check before trimming: tabs/newlines must not disappear into valid names.
    if isinstance(value, str) and any(
        unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in value
    ):
        raise ValueError("Owner contains unsupported characters")
    return value


OwnerName = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100),
    BeforeValidator(validate_owner_characters),
]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: OwnerName
    currency: Literal["USD"]


class Account(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: str
    owner: str
    currency: Literal["USD"]
    balance_cents: StrictInt = 0


class AccountBalance(BaseModel):
    account_id: str
    balance_cents: StrictInt
    currency: Literal["USD"]


class ErrorResponse(BaseModel):
    detail: str
