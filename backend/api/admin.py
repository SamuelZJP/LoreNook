from fastapi import APIRouter, Request

from backend.api.access import account_of
from backend.api.dependencies import DatabaseDependency
from backend.modules.admin.service import AdminService
from backend.repository.admin import AdminRepository
from backend.schemas.admin import AdminBatch, AdminBatchResult, AdminSnapshot, AdminTableInfo
from backend.shared.scope import SYSTEM, scoped

# Raw access to every user's rows; the app mounts it for administrators only.
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/schema", response_model=list[AdminTableInfo])
def schema(database: DatabaseDependency):
    with database.read() as session:
        return AdminService(AdminRepository(session)).catalog()


@router.get("/data", response_model=AdminSnapshot)
def read(database: DatabaseDependency, include_secrets: bool = False):
    with scoped(SYSTEM), database.read() as session:
        return AdminService(AdminRepository(session)).snapshot(include_secrets=include_secrets)


@router.post("/data", response_model=AdminBatchResult)
def apply(payload: AdminBatch, request: Request, database: DatabaseDependency):
    with scoped(SYSTEM), database.transaction() as session:
        return AdminService(AdminRepository(session)).apply(payload, account_of(request).id)
