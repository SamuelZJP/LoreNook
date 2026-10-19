from backend.modules.state.schema import StateValidator, checked_state, validate_state
from backend.modules.state.service import StateService
from backend.repository.database import Database
from backend.repository.queries import Repository
from backend.schemas.chats import StateRead
from backend.shared.errors import ConflictError


def replace_latest_state(database: Database, chat_id: str, content: dict, *,
                         validator: StateValidator = validate_state) -> StateRead:
    with database.read() as session:
        state, source = StateService(Repository(session)).editable(chat_id)
    checked = checked_state(validator, source, content)
    with database.transaction() as session:
        service = StateService(Repository(session))
        current, current_source = service.editable(chat_id)
        if current_source != source or current.model_dump_json() != state.model_dump_json():
            raise ConflictError("校验期间状态或 Schema 已变化，请重新提交")
        return service.replace(state, checked)
