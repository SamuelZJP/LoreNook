from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from backend.api.access import COOKIE, account_of
from backend.api.auth import client_address
from backend.api.dependencies import DatabaseDependency
from backend.demo.passes import DemoLinkError, DemoPasses
from backend.demo.schemas import DemoStatus, RedeemRequest, RedeemResult
from backend.shared import scope as scopes
from backend.shared.errors import NotFoundError

router = APIRouter(prefix="/api/demo", tags=["demo"])
REDEEM = "/api/demo/redeem"


@router.post("/redeem", response_model=RedeemResult)
async def redeem(payload: RedeemRequest, request: Request, response: Response, database: DatabaseDependency):
    throttle = request.app.state.login_throttle
    client = client_address(request)
    keys = (f"demo:{client}",) if client else ()
    wait = throttle.wait_seconds(*keys)
    if wait:
        raise HTTPException(status_code=429, detail=f"尝试次数过多，请 {wait} 秒后再试",
                            headers={"retry-after": str(wait)})

    def attempt():
        with scopes.scoped(scopes.SYSTEM), database.transaction() as session:
            return DemoPasses(session).redeem(payload.token, request.app.state.demo_template)

    try:
        result = await run_in_threadpool(attempt)
    except DemoLinkError:
        throttle.failed(*keys)
        raise
    seconds = max(1, int((result.expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(COOKIE, result.session_token, max_age=seconds, httponly=True,
                        secure=request.app.state.cookie_secure, samesite="lax", path="/")
    return RedeemResult(chat_id=result.chat_id)


@router.get("/status", response_model=DemoStatus)
def status(request: Request, database: DatabaseDependency):
    account = account_of(request)
    with scopes.scoped(scopes.SYSTEM), database.read() as session:
        record = DemoPasses(session).of_user(account.id) if account.role == "demo" else None
        if record is None:
            raise NotFoundError("当前账号不是体验账号")
        return DemoStatus(expires_at=record.expires_at, rounds_left=max(0, record.rounds_limit - record.rounds_used),
                          images_left=max(0, record.images_limit - record.images_used))
