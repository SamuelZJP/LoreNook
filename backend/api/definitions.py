"""Definition routes share operations while retaining explicit owner scopes."""

from fastapi import APIRouter, Response

from backend.api.dependencies import DatabaseDependency
from backend.modules.definitions.service import DefinitionService
from backend.repository.models import Character, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.catalog import DefinitionInput, DefinitionRead
from backend.schemas.definitions import ChatResolvedDefinitions, DefinitionPatch, DefinitionReorder
from backend.workflows.resolve_definitions import resolve_chat_definitions

router = APIRouter(prefix="/api", tags=["definitions"])


def owner_routes(prefix: str, model: type[Character | UserIdentity], chat_local: bool) -> APIRouter:
    scoped = APIRouter(prefix=prefix)

    def service(repository, owner_id):
        chat_id = owner_id if chat_local else None
        record_id = repository.owner_id(chat_id, model) if chat_local else owner_id
        owner = {"character_id": record_id} if model is Character else {"user_identity_id": record_id}
        return DefinitionService(repository, chat_id=chat_id, **owner)

    @scoped.get("", response_model=list[DefinitionRead])
    def list_definitions(owner_id: str, database: DatabaseDependency):
        with database.read() as session:
            return service(Repository(session), owner_id).list()

    @scoped.post("", response_model=DefinitionRead, status_code=201)
    def create_definition(owner_id: str, payload: DefinitionInput, database: DatabaseDependency):
        with database.transaction() as session:
            return service(Repository(session), owner_id).create(payload)

    @scoped.put("/reorder", response_model=list[DefinitionRead])
    def reorder_definitions(owner_id: str, payload: DefinitionReorder, database: DatabaseDependency):
        with database.transaction() as session:
            return service(Repository(session), owner_id).reorder(payload)

    @scoped.get("/{definition_id}", response_model=DefinitionRead)
    def read_definition(owner_id: str, definition_id: str, database: DatabaseDependency):
        with database.read() as session:
            return service(Repository(session), owner_id).read(definition_id)

    @scoped.patch("/{definition_id}", response_model=DefinitionRead)
    def update_definition(owner_id: str, definition_id: str, payload: DefinitionPatch, database: DatabaseDependency):
        with database.transaction() as session:
            return service(Repository(session), owner_id).update(definition_id, payload)

    @scoped.delete("/{definition_id}", status_code=204)
    def delete_definition(owner_id: str, definition_id: str, database: DatabaseDependency):
        with database.transaction() as session:
            service(Repository(session), owner_id).delete(definition_id)
        return Response(status_code=204)

    return scoped


router.include_router(owner_routes("/characters/{owner_id}/definitions", Character, False))
router.include_router(owner_routes("/user-identities/{owner_id}/definitions", UserIdentity, False))
router.include_router(owner_routes("/chats/{owner_id}/character/definitions", Character, True))
router.include_router(owner_routes("/chats/{owner_id}/user-identity/definitions", UserIdentity, True))


@router.post("/chats/{chat_id}/definitions/resolve", response_model=ChatResolvedDefinitions)
def resolve_definitions(chat_id: str, database: DatabaseDependency):
    return resolve_chat_definitions(database, chat_id)
