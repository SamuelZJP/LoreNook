"""The status bar tables as data management sees them: storage types only."""

from backend.modules.admin.registry import register_table
from backend.schemas.admin import RecordId
from backend.schemas.common import Contract
from backend.status_bar.models import CharacterStatusBar, ChatStatusBarSettings


class CharacterStatusBarRow(Contract):
    character_id: RecordId
    code: str


class StatusBarSettingsRow(Contract):
    chat_id: RecordId
    enabled: bool = True


def register_admin_tables() -> None:
    register_table(CharacterStatusBar, CharacterStatusBarRow)
    register_table(ChatStatusBarSettings, StatusBarSettingsRow)
