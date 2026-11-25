"""Export a character as a card file, and import one as a new library character."""

from pydantic import ValidationError

from backend.modules.character_cards.convert import card_from_character, character_from_card, has_code
from backend.modules.character_cards.format import CardFile, describe, dump_card, parse_card
from backend.modules.character_cards.media import MediaReader, MediaWriter
from backend.modules.character_cards.package import Package, read_package, write_package
from backend.modules.character_cards.sections import SECTIONS
from backend.modules.characters.service import CharacterService
from backend.modules.media import MediaStorage
from backend.modules.state.initial import InitialStateFactory
from backend.repository.database import Database
from backend.repository.models import Character
from backend.repository.queries import Repository
from backend.schemas.catalog import CharacterRead
from backend.schemas.character_cards import CardSummary
from backend.shared.errors import CharacterCardError


def export_card(database: Database, storage: MediaStorage, character_id: str | None = None,
                chat_id: str | None = None) -> tuple[str, bytes]:
    """(character name, file). With `chat_id`, the chat's own character; otherwise a library one."""
    media = MediaWriter(storage)
    with database.read() as session:
        repository = Repository(session)
        if chat_id is not None:
            character_id = repository.owner_id(chat_id, Character)
        character = CharacterService(repository).read(character_id, chat_id)
        features = {}
        for name, section in SECTIONS.items():
            data = section.export(session, character.id, media)
            if data is not None:
                features[name] = data
    card = CardFile(character=card_from_character(character, media), features=features)
    return character.name, write_package(Package(card=dump_card(card), media=media.files))


def _open(data: bytes) -> tuple[CardFile, Package]:
    package = read_package(data)
    return parse_card(package.card), package


def inspect_card(data: bytes) -> CardSummary:
    card, _ = _open(data)
    code = has_code(card.character)
    return CardSummary(name=card.character.name, scenes=len(card.character.scenes),
                       has_state_schema=code["state_schema"], has_state_script=code["state_script"],
                       features=[name for name in card.features if name in SECTIONS],
                       unknown_features=[name for name in card.features if name not in SECTIONS])


def import_card(database: Database, storage: MediaStorage, initial_state_factory: InitialStateFactory,
                data: bytes, keep_code: bool) -> CharacterRead:
    """Always a new library character. Images are stored first; any later failure leaves them unreferenced."""
    card, package = _open(data)
    media = MediaReader(storage, package.media)
    payload = character_from_card(card.character, media, keep_code)
    with database.transaction() as session:
        repository = Repository(session)
        service = CharacterService(repository, initial_state_factory)
        character = service.create(payload, check_scenes=keep_code or not has_code(card.character)["state_schema"])
        for name, section_data in card.features.items():
            section = SECTIONS.get(name)
            if section is None:
                continue
            try:
                section.import_(session, character.id, section_data, media)
            except ValidationError as error:
                raise CharacterCardError(f"功能数据 {name} 格式不对：" + describe(error)) from error
        session.flush()
        return service.read(character.id)
