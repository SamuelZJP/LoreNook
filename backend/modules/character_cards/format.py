"""The card.json contract. Bump VERSION only for changes an older LoreNook can't read."""

import json
from typing import Annotated

from pydantic import Field, JsonValue, ValidationError

from backend.schemas.common import Contract, Name, StateScriptHistory
from backend.shared.errors import CharacterCardError

FORMAT = "lorenook.character"
VERSION = 1


class CardDefinition(Contract):
    enabled: bool = True
    has_template: bool = False
    content: str


class CardScene(Contract):
    name: Name
    description: str = ""
    first_message: str = ""
    initial_state: dict[str, JsonValue] = Field(default_factory=dict)


class CardCharacter(Contract):
    """Like CharacterCreate, without IDs or order fields; images are package paths or outside URLs."""
    name: Name
    avatar: str | None = None
    portrait: str | None = None
    description: str = ""
    definitions: list[CardDefinition] = Field(default_factory=list)
    scenes: Annotated[list[CardScene], Field(min_length=1)]
    state_schema: str = ""
    state_reference: str = ""
    state_update_rules: str = ""
    state_script: str = ""
    state_script_history: StateScriptHistory = 0


class CardFile(Contract):
    format: str = FORMAT
    version: int = VERSION
    character: CardCharacter
    # Each feature owns its entry; the core only checks that it is an object.
    features: dict[str, dict[str, JsonValue]] = Field(default_factory=dict)


def describe(error: ValidationError, limit: int = 3) -> str:
    """A short, value-free description of what is wrong."""
    parts = [f"{'.'.join(str(part) for part in item['loc']) or '根'}：{item['msg']}" for item in error.errors()[:limit]]
    more = error.error_count() - limit
    return "；".join(parts) + (f"；另有 {more} 处" if more > 0 else "")


def parse_card(raw: bytes) -> CardFile:
    try:
        header = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CharacterCardError("card.json 不是有效的 JSON") from error
    if not isinstance(header, dict) or header.get("format") != FORMAT:
        raise CharacterCardError("不是 LoreNook 角色卡")
    version = header.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CharacterCardError("角色卡版本无效")
    if version > VERSION:
        raise CharacterCardError(f"角色卡版本 {version} 高于当前支持的 {VERSION}，请先升级 LoreNook")
    try:
        return CardFile.model_validate_json(raw)
    except ValidationError as error:
        raise CharacterCardError("card.json 格式不对：" + describe(error)) from error


def dump_card(card: CardFile) -> bytes:
    return json.dumps(card.model_dump(mode="json"), ensure_ascii=False, indent=2).encode("utf-8")
