"""Application entry point. Database upgrades are run explicitly with Alembic."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
import httpx

from backend.api.catalog import router as catalog_router
from backend.api.chats import router as chats_router
from backend.api.definitions import router as definitions_router
from backend.api.memory import router as memory_router
from backend.api.presets import router as presets_router
from backend.api.models import router as models_router
from backend.api.writing import router as writing_router
from backend.api.state import router as state_router
from backend.api.round_summary import router as round_summary_router
from backend.api.episode_decision import router as episode_decision_router
from backend.api.episode_summary import router as episode_summary_router
from backend.api.archive import router as archive_router
from backend.api.admin import router as admin_router
from backend.api.media import router as media_router
from backend.api.errors import register_error_handlers
from backend.config import Settings
from backend.features import FEATURES
from backend.llm.client import ModelClient
from backend.modules.media import MediaStorage
from backend.modules.state.initial import InitialStateFactory
from backend.modules.state.schema import StateValidator, python_initial_state, validate_state
from backend.repository.database import Database
from backend.shared.hooks import AppHooks


def create_app(
    settings: Settings | None = None,
    initial_state_factory: InitialStateFactory = python_initial_state,
    *, llm_transport: httpx.BaseTransport | None = None,
    state_validator: StateValidator = validate_state,
    **feature_options,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configuration = settings or Settings()
        database = Database(configuration)
        app.state.database = database
        app.state.initial_state_factory = initial_state_factory
        app.state.state_validator = state_validator
        app.state.state_recent_summaries = configuration.state_recent_summaries
        app.state.round_summary_recent_summaries = configuration.round_summary_recent_summaries
        client = ModelClient(transport=llm_transport, timeout_seconds=configuration.llm_timeout_seconds,
                             max_response_bytes=configuration.llm_max_response_bytes,
                             recording_directory=configuration.llm_recording_directory)
        app.state.model_client = client
        app.state.media = MediaStorage(configuration.resolved_media_directory())
        app.state.hooks = AppHooks()
        stops = [feature.start(app, configuration, database, client, **feature_options) for feature in FEATURES]
        try:
            yield
        finally:
            for stop in reversed(stops):
                stop()
            client.close()
            database.dispose()

    app = FastAPI(title="LoreNook", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(catalog_router)
    app.include_router(chats_router)
    app.include_router(definitions_router)
    app.include_router(memory_router)
    app.include_router(presets_router)
    app.include_router(models_router)
    app.include_router(writing_router)
    app.include_router(state_router)
    app.include_router(round_summary_router)
    app.include_router(episode_decision_router)
    app.include_router(episode_summary_router)
    app.include_router(archive_router)
    app.include_router(admin_router)
    app.include_router(media_router)
    for feature in FEATURES:
        feature.install(app)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
