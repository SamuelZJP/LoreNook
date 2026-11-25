"""The feature's single connection to the application: routes, the request check, errors and the sweeper."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api.access import register_public_route, register_request_check
from backend.demo import models as _models  # noqa: F401  (registers the table)
from backend.demo.api import REDEEM, router
from backend.demo.passes import DemoLinkError, DemoUnavailableError
from backend.demo.policy import check_demo_request
from backend.demo.sweeper import Sweeper

register_public_route(REDEEM)
register_request_check(check_demo_request)


def install(app: FastAPI) -> None:
    app.include_router(router)

    @app.exception_handler(DemoLinkError)
    async def link_error(request: Request, error: DemoLinkError):
        return JSONResponse(status_code=410, content={"detail": str(error)})

    @app.exception_handler(DemoUnavailableError)
    async def unavailable(request: Request, error: DemoUnavailableError):
        return JSONResponse(status_code=503, content={"detail": str(error)})


def start(app: FastAPI, configuration, database, client, *, demo_sweeper: bool = True, **_):
    """Returns the matching shutdown function."""
    app.state.demo_template = configuration.demo_template
    if not demo_sweeper:
        return lambda: None
    sweeper = Sweeper(database, app.state.hooks)
    sweeper.start()
    return sweeper.stop
