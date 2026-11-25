"""Feature data on a card, under `features.<name>`. Features register here, without the core knowing them."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.modules.character_cards.media import MediaReader, MediaWriter


@dataclass(frozen=True)
class CardSection:
    # (session, character_id, media) -> the section's data, or None to leave it out
    export: Callable[[Session, str, MediaWriter], dict[str, Any] | None]
    # (session, character_id, data, media), inside the import transaction; raising aborts the import
    import_: Callable[[Session, str, dict[str, Any], MediaReader], None]


SECTIONS: dict[str, CardSection] = {}


def register_card_section(name: str, export, import_) -> None:
    SECTIONS[name] = CardSection(export=export, import_=import_)
