from fastapi import APIRouter, Request, Response
from pydantic import JsonValue

from backend.api.dependencies import DatabaseDependency
from backend.modules.characters.code import check_code_allowed
from backend.modules.characters.service import CharacterService
from backend.modules.state.initial import build_initial_state
from backend.modules.users.service import IdentityService
from backend.repository.queries import Repository
from backend.schemas.catalog import (
    CharacterCreate, CharacterPatch, CharacterRead, IdentityCreate, IdentityPatch, IdentityRead, InitialStatePreview,
)

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/characters", response_model=list[CharacterRead])
def list_characters(database: DatabaseDependency):
    with database.read() as session:
        return CharacterService(Repository(session)).list_library()


@router.post("/characters", response_model=CharacterRead, status_code=201)
def create_character(payload: CharacterCreate, request: Request, database: DatabaseDependency):
    with database.transaction() as session:
        return CharacterService(Repository(session), request.app.state.initial_state_factory).create(payload)


@router.post("/characters/initial-state-preview", response_model=dict[str, JsonValue])
def preview_initial_state(payload: InitialStatePreview, request: Request):
    """Compute a scene's full initial state from an unsaved Schema draft; nothing is stored."""
    check_code_allowed(payload.state_schema)
    return build_initial_state(request.app.state.initial_state_factory, payload.state_schema, payload.initial_state)


@router.get("/characters/{character_id}", response_model=CharacterRead)
def read_character(character_id: str, database: DatabaseDependency):
    with database.read() as session:
        return CharacterService(Repository(session)).read(character_id)


@router.patch("/characters/{character_id}", response_model=CharacterRead)
def update_character(character_id: str, payload: CharacterPatch, request: Request, database: DatabaseDependency):
    with database.transaction() as session:
        return CharacterService(Repository(session), request.app.state.initial_state_factory).update(character_id, payload)


@router.delete("/characters/{character_id}", status_code=204)
def delete_character(character_id: str, database: DatabaseDependency):
    with database.transaction() as session:
        CharacterService(Repository(session)).delete_source(character_id)
    return Response(status_code=204)


@router.get("/user-identities", response_model=list[IdentityRead])
def list_identities(database: DatabaseDependency):
    with database.read() as session:
        return IdentityService(Repository(session)).list_library()


@router.post("/user-identities", response_model=IdentityRead, status_code=201)
def create_identity(payload: IdentityCreate, database: DatabaseDependency):
    with database.transaction() as session:
        return IdentityService(Repository(session)).create(payload)


@router.get("/user-identities/{identity_id}", response_model=IdentityRead)
def read_identity(identity_id: str, database: DatabaseDependency):
    with database.read() as session:
        return IdentityService(Repository(session)).read(identity_id)


@router.patch("/user-identities/{identity_id}", response_model=IdentityRead)
def update_identity(identity_id: str, payload: IdentityPatch, database: DatabaseDependency):
    with database.transaction() as session:
        return IdentityService(Repository(session)).update(identity_id, payload)


@router.delete("/user-identities/{identity_id}", status_code=204)
def delete_identity(identity_id: str, database: DatabaseDependency):
    with database.transaction() as session:
        IdentityService(Repository(session)).delete_source(identity_id)
    return Response(status_code=204)
