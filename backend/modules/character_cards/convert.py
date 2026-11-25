"""A card to and from a character, as plain data."""

from backend.modules.character_cards.format import CardCharacter, CardDefinition, CardScene
from backend.modules.character_cards.media import MediaReader, MediaWriter
from backend.schemas.catalog import CharacterCreate, CharacterRead, DefinitionInput, SceneInput

CODE_FIELDS = ("state_schema", "state_script")


def card_from_character(character: CharacterRead, media: MediaWriter) -> CardCharacter:
    return CardCharacter(
        name=character.name, avatar=media.url(character.avatar), portrait=media.url(character.portrait),
        description=character.description,
        definitions=[CardDefinition(enabled=d.enabled, has_template=d.has_template, content=d.content)
                     for d in sorted(character.definitions, key=lambda d: d.order)],
        scenes=[CardScene(name=s.name, description=s.description, first_message=s.first_message,
                          initial_state=s.initial_state) for s in sorted(character.scenes, key=lambda s: s.order)],
        **character.model_dump(include={"state_schema", "state_reference", "state_update_rules", "state_script",
                                        "state_script_history"}),
    )


def character_from_card(card: CardCharacter, media: MediaReader, keep_code: bool) -> CharacterCreate:
    values = card.model_dump(exclude={"avatar", "portrait", "definitions", "scenes"})
    if not keep_code:
        values.update({name: "" for name in CODE_FIELDS})
    return CharacterCreate(
        **values, avatar=media.url(card.avatar), portrait=media.url(card.portrait),
        definitions=[DefinitionInput(order=order, **d.model_dump()) for order, d in enumerate(card.definitions)],
        scenes=[SceneInput(order=order, **s.model_dump()) for order, s in enumerate(card.scenes)],
    )


def has_code(card: CardCharacter) -> dict[str, bool]:
    return {name: bool(getattr(card, name).strip()) for name in CODE_FIELDS}
