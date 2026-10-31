from sqlalchemy.orm.attributes import flag_modified

from backend.repository.models import Character, StateSnapshot
from backend.repository.queries import Repository
from backend.schemas.chats import StateRead
from backend.shared.errors import ConflictError


class StateService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def latest(self, chat_id: str) -> StateRead:
        character_id = self.repository.owner_id(chat_id, Character)
        state = self.repository.latest_state(character_id)
        if state is None:
            raise ConflictError("Chat has no state snapshot")
        return StateRead.model_validate(state)

    def editable(self, chat_id: str) -> tuple[StateRead, str]:
        state = self.latest(chat_id)
        latest = self.repository.latest_round(chat_id)
        if latest is not None and (latest.archive_step != "complete" or state.round_id != latest.id):
            raise ConflictError("只能编辑初始状态或最新已归档回合的状态")
        character = self.repository.get(Character, state.character_id)
        return state, character.state_schema

    def replace(self, expected: StateRead, content: dict) -> StateRead:
        state = self.repository.get(StateSnapshot, expected.id)
        state.content = content
        # JSON's Python equality conflates 1 and True; force the requested type change.
        flag_modified(state, "content")
        self.repository.session.flush()
        return StateRead.model_validate(state)
