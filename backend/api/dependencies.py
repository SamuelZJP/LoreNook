from typing import Annotated

from fastapi import Depends, Request

from backend.repository.database import Database
from backend.llm.client import ModelClient


def get_database(request: Request) -> Database:
    return request.app.state.database


DatabaseDependency = Annotated[Database, Depends(get_database)]


def get_model_client(request: Request) -> ModelClient:
    return request.app.state.model_client


ModelClientDependency = Annotated[ModelClient, Depends(get_model_client)]
