from backend.repository.models import Definition
from backend.repository.queries import Repository
from backend.schemas.catalog import DefinitionInput, DefinitionRead


class DefinitionStorage:
    def __init__(self, repository: Repository):
        self.repository = repository

    def read(self, *, character_id=None, user_identity_id=None) -> list[DefinitionRead]:
        return [DefinitionRead.model_validate(record) for record in self.repository.definitions(
            character_id=character_id, user_identity_id=user_identity_id
        )]

    def replace(self, definitions: list[DefinitionInput], *, character_id=None, user_identity_id=None):
        # Validate scope before deleting; all changes participate in the caller's transaction.
        for record in self.repository.definitions(character_id=character_id, user_identity_id=user_identity_id):
            self.repository.delete(record)
        for item in definitions:
            self.repository.add(Definition(
                character_id=character_id, user_identity_id=user_identity_id,
                **item.model_dump(include={"order", "enabled", "has_template", "content"}),
            ))
