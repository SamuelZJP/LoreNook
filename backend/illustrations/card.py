"""The cast on a character card file, under `features.illustrations`."""

from pydantic import Field

from backend.illustrations.schemas import CastMemberInput
from backend.illustrations.service import CastService
from backend.modules.character_cards.sections import register_card_section
from backend.repository.queries import Repository
from backend.schemas.common import Contract, Name


class CardCastMember(Contract):
    name: Name
    appearance: str = ""
    # A package path, media/…
    reference_image: str | None = None


class CardIllustrations(Contract):
    cast: list[CardCastMember] = Field(default_factory=list)


def export(session, character_id, media):
    members = CastService(Repository(session)).members(character_id)
    if not members:
        return None
    return CardIllustrations(cast=[CardCastMember(name=m.name, appearance=m.appearance,
                                                  reference_image=media.name(m.reference_image))
                                   for m in members]).model_dump(mode="json")


def import_(session, character_id, data, media):
    card = CardIllustrations.model_validate(data)
    CastService(Repository(session)).replace(character_id, [
        CastMemberInput(name=m.name, appearance=m.appearance, reference_image=media.name(m.reference_image))
        for m in card.cast])


def register_card_sections() -> None:
    register_card_section("illustrations", export, import_)
