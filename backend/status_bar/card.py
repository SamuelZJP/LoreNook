"""The status bar code on a character card file, under `features.status_bar`."""

from backend.modules.character_cards.sections import register_card_section
from backend.repository.queries import Repository
from backend.schemas.common import Contract
from backend.status_bar.service import StatusBarService


class CardStatusBar(Contract):
    code: str = ""


def export(session, character_id, media):
    code = StatusBarService(Repository(session)).read(character_id).code
    return CardStatusBar(code=code).model_dump() if code.strip() else None


def import_(session, character_id, data, media):
    StatusBarService(Repository(session)).replace(character_id, CardStatusBar.model_validate(data).code)


def register_card_sections() -> None:
    register_card_section("status_bar", export, import_)
