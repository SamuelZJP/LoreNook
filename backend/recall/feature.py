"""The feature's single connection to the application: routes, errors and tables."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.recall.admin_tables import register_admin_tables
from backend.recall.api import router
from backend.recall.errors import RecallError

register_admin_tables()


def install(app: FastAPI) -> None:
    app.include_router(router)

    @app.exception_handler(RecallError)
    async def recall_error(request: Request, error: RecallError):
        return JSONResponse(status_code=422, content={"detail": str(error)})


def start(app: FastAPI, configuration, database, client, **_):
    """Recall has no background services to run."""
    return lambda: None
