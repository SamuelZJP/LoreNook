from fastapi import APIRouter

from backend.api.dependencies import DatabaseDependency
from backend.modules.admin.service import AdminService
from backend.repository.admin import AdminRepository
from backend.schemas.admin import AdminBatch, AdminBatchResult, AdminSnapshot, AdminTableInfo

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/schema", response_model=list[AdminTableInfo])
def schema(database: DatabaseDependency):
    with database.read() as session:
        return AdminService(AdminRepository(session)).catalog()


@router.get("/data", response_model=AdminSnapshot)
def read(database: DatabaseDependency, include_secrets: bool = False):
    with database.read() as session:
        return AdminService(AdminRepository(session)).snapshot(include_secrets=include_secrets)


@router.post("/data", response_model=AdminBatchResult)
def apply(payload: AdminBatch, database: DatabaseDependency):
    with database.transaction() as session:
        return AdminService(AdminRepository(session)).apply(payload)
