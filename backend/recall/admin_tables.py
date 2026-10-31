"""The recall table as data management sees it: storage types only."""

from backend.modules.admin.registry import register_table
from backend.recall.models import ChatRecallSettings
from backend.recall.schemas import DEFAULT_DEPTH, DEFAULT_EPISODE_LIMIT, DEFAULT_SUMMARY_LIMIT
from backend.schemas.admin import RecordId
from backend.schemas.common import Contract, NonnegativeInt


class RecallSettingsRow(Contract):
    chat_id: RecordId
    enabled: bool = False
    model_config_id: RecordId | None = None
    depth: NonnegativeInt = DEFAULT_DEPTH
    episode_limit: NonnegativeInt = DEFAULT_EPISODE_LIMIT
    summary_limit: NonnegativeInt = DEFAULT_SUMMARY_LIMIT


def register_admin_tables() -> None:
    register_table(ChatRecallSettings, RecallSettingsRow)
