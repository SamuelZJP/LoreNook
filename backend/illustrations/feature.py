"""The feature's single connection to the application: routes, errors, tables, card section, hooks and lifecycle."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.illustrations.admin_tables import register_admin_tables
from backend.illustrations.card import register_card_sections
from backend.illustrations.api import router
from backend.illustrations.comfyui import ComfyUIClient
from backend.illustrations.errors import IllustrationError
from backend.illustrations.jobs import IllustrationRunner, interrupt_unfinished
from backend.illustrations.progress import ProgressBoard
from backend.illustrations.service import CastService
from backend.illustrations.storage import ImageStorage
from backend.repository.queries import Repository

register_admin_tables()
register_card_sections()


def install(app: FastAPI) -> None:
    app.include_router(router)

    @app.exception_handler(IllustrationError)
    async def illustration_error(request: Request, error: IllustrationError):
        return JSONResponse(status_code=422, content={"detail": str(error)})


def start(app: FastAPI, configuration, database, client, *, comfyui_transport=None, comfyui_connect=None,
          illustration_executor=None, **_):
    """Returns the matching shutdown function."""
    comfy = ComfyUIClient(transport=comfyui_transport, timeout_seconds=configuration.comfyui_timeout_seconds,
                          poll_seconds=configuration.comfyui_poll_seconds, connect=comfyui_connect)
    storage = ImageStorage(configuration.resolved_image_directory())
    interrupt_unfinished(database)
    board = ProgressBoard()
    runner = IllustrationRunner(database, comfy, storage, app.state.media, board, illustration_executor)
    app.state.illustration_progress = board
    app.state.image_storage = storage
    app.state.illustrations = runner

    hooks = app.state.hooks
    hooks.round_archived.append(runner.round_archived)
    hooks.chat_deleted.append(storage.remove_chat)
    hooks.chat_created.append(lambda session, chat_id, payload:
                              CastService(Repository(session)).copy_for_chat(session, chat_id, payload))

    def stop() -> None:
        runner.close()
        comfy.close()
    return stop
