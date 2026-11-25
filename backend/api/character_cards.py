import re
from urllib.parse import quote

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from backend.api.dependencies import DatabaseDependency
from backend.api.uploads import read_body
from backend.modules.character_cards.package import MAX_PACKAGE_BYTES
from backend.schemas.catalog import CharacterRead
from backend.schemas.character_cards import CardSummary
from backend.workflows.character_card import export_card, import_card, inspect_card

router = APIRouter(prefix="/api", tags=["character cards"])
EXTENSION = ".lorenook"
UNSAFE = re.compile(r'[\x00-\x1f\x7f/\\:*?"<>|]')


def _download(name: str, data: bytes) -> Response:
    filename = (UNSAFE.sub("", name).strip(" .")[:100] or "角色卡") + EXTENSION
    return Response(data, media_type="application/zip", headers={
        "content-disposition": f"attachment; filename=\"character{EXTENSION}\"; filename*=UTF-8''{quote(filename)}",
    })


async def _card_body(request: Request) -> bytes:
    return await read_body(request, MAX_PACKAGE_BYTES, f"角色卡不能超过 {MAX_PACKAGE_BYTES // (1024 * 1024)} MB")


@router.get("/characters/{character_id}/card")
def export_library_card(character_id: str, request: Request, database: DatabaseDependency):
    return _download(*export_card(database, request.app.state.media, character_id=character_id))


@router.get("/chats/{chat_id}/character/card")
def export_chat_card(chat_id: str, request: Request, database: DatabaseDependency):
    return _download(*export_card(database, request.app.state.media, chat_id=chat_id))


@router.post("/character-cards/inspect", response_model=CardSummary)
async def inspect(request: Request):
    """The request body is the card file. Nothing is stored."""
    return await run_in_threadpool(inspect_card, await _card_body(request))


@router.post("/character-cards/import", response_model=CharacterRead, status_code=201)
async def import_(request: Request, database: DatabaseDependency, keep_code: bool = False):
    """The request body is the card file. Without `keep_code`, the card's Schema and state script are dropped."""
    return await run_in_threadpool(import_card, database, request.app.state.media,
                                   request.app.state.initial_state_factory, await _card_body(request), keep_code)
