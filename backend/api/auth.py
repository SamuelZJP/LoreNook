import ipaddress

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from backend.api.access import COOKIE, account_of
from backend.api.dependencies import DatabaseDependency
from backend.modules.accounts.service import SESSION_DAYS, AccountService
from backend.repository.accounts import AccountRepository
from backend.schemas.accounts import AccountRead, LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client(request: Request) -> str | None:
    """The visitor's public address, or None when only a proxy's address is known.

    Behind the proxy chain every request may come from 127.0.0.1; throttling that would lock everyone out.
    """
    forwarded = request.headers.get("x-forwarded-for")
    address = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    try:
        return address if ipaddress.ip_address(address).is_global else None
    except ValueError:
        return None


@router.post("/login", response_model=AccountRead)
async def login(payload: LoginRequest, request: Request, response: Response, database: DatabaseDependency):
    throttle = request.app.state.login_throttle
    client = _client(request)
    keys = (f"user:{payload.username.lower()}",) + ((f"client:{client}",) if client else ())
    wait = throttle.wait_seconds(*keys)
    if wait:
        raise HTTPException(status_code=429, detail=f"尝试次数过多，请 {wait} 秒后再试",
                            headers={"retry-after": str(wait)})

    def attempt():
        with database.transaction() as session:
            return AccountService(AccountRepository(session)).login(payload.username, payload.password)

    result = await run_in_threadpool(attempt)
    if result is None:
        throttle.failed(*keys)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    throttle.succeeded(*keys)
    token, account = result
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=request.app.state.cookie_secure, samesite="lax", path="/")
    return AccountRead(username=account.username, role=account.role)


@router.post("/logout", status_code=204)
def logout(request: Request, database: DatabaseDependency):
    token = request.cookies.get(COOKIE)
    if token:
        with database.transaction() as session:
            AccountService(AccountRepository(session)).logout(token)
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=request.app.state.cookie_secure, samesite="lax")
    return response


@router.get("/me", response_model=AccountRead)
def me(request: Request):
    account = account_of(request)
    return AccountRead(username=account.username, role=account.role)
