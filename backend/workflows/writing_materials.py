"""Shared database snapshot and material resolution for preview and generation."""

from copy import deepcopy
from dataclasses import dataclass

from pydantic import JsonValue

from backend.modules.chats.service import ChatService
from backend.modules.definitions.renderer import DefinitionRenderer, substitute_names
from backend.modules.definitions.storage import DefinitionStorage
from backend.modules.memory.service import MemoryService
from backend.repository.models import Character, Chat, UserIdentity, WritingPreset
from backend.repository.queries import Repository
from backend.schemas.catalog import DefinitionRead
from backend.schemas.memory import MemoryHistory
from backend.schemas.presets import WritingMaterials
from backend.shared.errors import ConflictError


@dataclass(frozen=True)
class WritingSnapshot:
    chat_id: str
    preset_id: str
    source: str
    state_snapshot_id: str
    based_on_round_id: str | None
    character_name: str
    user_identity_name: str
    first_message: str
    state: dict[str, JsonValue]
    character_definitions: list[DefinitionRead]
    user_definitions: list[DefinitionRead]
    history: MemoryHistory


def collect_writing_snapshot(repository: Repository, chat_id: str) -> WritingSnapshot:
    """Caller keeps this read in the same transaction as model configuration selection."""
    chat = repository.get(Chat, chat_id)
    latest = repository.latest_round(chat_id)
    if latest is not None and latest.archive_step != "complete":
        raise ConflictError("请先完成当前回合归档")
    if chat.writing_preset_id is None:
        raise ConflictError("聊天尚未选择写作预设")
    preset = repository.get_owned(WritingPreset, chat.writing_preset_id, chat_id)
    service = ChatService(repository)
    character = repository.get(Character, service.owner_id(chat_id, Character))
    identity = repository.get(UserIdentity, service.owner_id(chat_id, UserIdentity))
    state = repository.latest_state(character.id)
    if state is None:
        raise ConflictError("Chat has no state snapshot")
    storage = DefinitionStorage(repository)
    history = MemoryService(repository).assemble(chat_id)
    return WritingSnapshot(
        chat_id=chat_id, preset_id=preset.id, source=preset.source,
        state_snapshot_id=state.id, based_on_round_id=latest.id if latest else None,
        character_name=character.name, user_identity_name=identity.name,
        first_message=repository.opening_scene(character.id).first_message, state=deepcopy(state.content),
        character_definitions=storage.read(character_id=character.id),
        user_definitions=storage.read(user_identity_id=identity.id),
        history=MemoryHistory.model_validate(history.model_dump(exclude={"chat_id", "uses_compressed_history"})),
    )


def with_instruction(user_input: str, instruction: str) -> str:
    """Text for this request only; the candidate and archive keep the raw input."""
    if not instruction.strip():
        return user_input
    block = f"<instruction>\n{instruction.strip()}\n</instruction>"
    return f"{user_input}\n\n{block}" if user_input.strip() else block


def resolve_writing_materials(snapshot: WritingSnapshot, user_input: str, instruction: str = "") -> WritingMaterials:
    """Render only after the database session has closed."""
    names = {"user_name": snapshot.user_identity_name, "character_name": snapshot.character_name}
    resolved = DefinitionRenderer().resolve(snapshot.character_definitions, snapshot.user_definitions,
                                            snapshot.state, **names)
    return WritingMaterials(
        character_name=snapshot.character_name, user_identity_name=snapshot.user_identity_name,
        first_message=substitute_names(snapshot.first_message, **names), state=snapshot.state, history=snapshot.history,
        user_input=with_instruction(user_input, instruction), **resolved.model_dump(),
    )
