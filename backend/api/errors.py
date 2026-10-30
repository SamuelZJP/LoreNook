import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError

from backend.shared.errors import (
    AdminDataError, ArchiveExecutionError, ConflictError, DefinitionTemplateError, ModelCallError, ModelConfigurationError,
    NotFoundError, PresetExecutionError, StateInitializationError,
    StateSchemaError, StateUpdateError,
    RoundSummaryError, EpisodeDecisionError, EpisodeSummaryError,
)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ArchiveExecutionError)
    async def archive_error(request: Request, error: ArchiveExecutionError):
        # Reuse the exact sanitized response of the failing module.
        handler = next(app.exception_handlers[kind] for kind in type(error.cause).__mro__
                       if kind in app.exception_handlers)
        response = await handler(request, error.cause)
        body = json.loads(response.body)
        body["archive"] = error.progress.model_dump(mode="json")
        return JSONResponse(status_code=response.status_code, content=body)

    @app.exception_handler(AdminDataError)
    @app.exception_handler(StateSchemaError)
    @app.exception_handler(StateUpdateError)
    @app.exception_handler(RoundSummaryError)
    @app.exception_handler(EpisodeDecisionError)
    @app.exception_handler(EpisodeSummaryError)
    async def state_error(request: Request, error: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, error: RequestValidationError):
        # Model-level validation errors can embed a complete input containing API keys.
        details = [{key: value for key, value in item.items() if key != "input"}
                   for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(details)})

    @app.exception_handler(ModelConfigurationError)
    async def model_configuration_error(request: Request, error: ModelConfigurationError):
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(ModelCallError)
    async def model_call_error(request: Request, error: ModelCallError):
        return JSONResponse(status_code=504 if error.kind == "timeout" else 502, content={"detail": {
            "kind": error.kind, "message": error.message, "upstream_status": error.upstream_status,
        }})

    @app.exception_handler(PresetExecutionError)
    async def preset_error(request: Request, error: PresetExecutionError):
        return JSONResponse(status_code=422, content={"detail": {
            "stage": error.stage, "message": error.message,
        }})

    @app.exception_handler(DefinitionTemplateError)
    async def template_error(request: Request, error: DefinitionTemplateError):
        return JSONResponse(status_code=422, content={"detail": {
            "definition_id": error.definition_id, "message": error.message, "line": error.line,
        }})

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, error: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, error: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(StateInitializationError)
    async def initial_state_error(request: Request, error: StateInitializationError):
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error: IntegrityError):
        # SQLAlchemy errors can contain bound values, including model credentials.
        return JSONResponse(status_code=409, content={"detail": "数据关联或唯一性约束冲突"})
