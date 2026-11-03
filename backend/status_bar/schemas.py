from typing import Annotated

from pydantic import Field

from backend.schemas.common import Contract

# One HTML document; generous, but keeps a pasted mistake from bloating every chat copy.
Code = Annotated[str, Field(max_length=512 * 1024)]


class StatusBar(Contract):
    """Empty code means the character has no status bar."""
    code: Code = ""


class ChatStatusBar(Contract):
    code: Code = ""
    enabled: bool = True


class ChatStatusBarPatch(Contract):
    code: Code | None = None
    enabled: bool | None = None
