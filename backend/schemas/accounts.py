from typing import Annotated

from pydantic import StringConstraints

from backend.schemas.common import Contract


class LoginRequest(Contract):
    username: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class AccountRead(Contract):
    username: str
    role: str
