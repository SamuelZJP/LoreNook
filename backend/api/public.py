"""What the public home page shows; no sign-in."""

from fastapi import APIRouter, Request

from backend.modules.presence import online_count
from backend.schemas.common import Contract

router = APIRouter(prefix="/api/public", tags=["public"])


class HomeInfo(Contract):
    online: int
    icp_number: str


@router.get("/home", response_model=HomeInfo)
def home(request: Request):
    return HomeInfo(online=online_count(), icp_number=request.app.state.icp_number)
