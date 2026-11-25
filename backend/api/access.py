"""Who is asking, and may they: the session cookie, the request's data scope, and the check every route passes.

`SessionMiddleware` resolves the cookie and sets the scope for the whole request. `guard` runs before every
route (an application-wide dependency, so a new route is protected without opting in): it requires a
signed-in user unless the route is public, requires an administrator where marked, and returns 404 for an
ID in the path that does not belong to the user. Rows reached through such an ID (a chat's rounds, say) are
then the user's too.
"""

from collections.abc import Callable
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.modules.accounts.service import Account, AccountService
from backend.repository.accounts import AccountRepository
from backend.repository.models import Character, Chat, ChatTemplate, ModelConfig, UserIdentity, WritingPreset
from backend.repository.queries import Repository
from backend.shared import scope as scopes

COOKIE = "lorenook_session"
PUBLIC_ROUTES = {"/health", "/api/auth/login", "/api/auth/logout", "/api/public/home"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Path parameters naming an owned row; features add theirs with `register_owned_parameter`.
OWNED_PARAMETERS: dict[str, type] = {
    "chat_id": Chat, "character_id": Character, "identity_id": UserIdentity, "config_id": ModelConfig,
    "preset_id": WritingPreset, "template_id": ChatTemplate,
}
# Path parameters naming a row inside a chat; every route with one also has `chat_id`, and queries use both.
CHAT_CHILD_PARAMETERS = {"round_id", "episode_id", "illustration_id"}
# Checked by the route itself.
SELF_CHECKED_PARAMETERS = {"name"}


# (request, account), after sign-in is confirmed; features raise HTTPException to refuse a request.
REQUEST_CHECKS: list[Callable[[Request, Account], None]] = []


def register_owned_parameter(name: str, model: type) -> None:
    OWNED_PARAMETERS[name] = model


def register_public_route(path: str) -> None:
    PUBLIC_ROUTES.add(path)


def register_request_check(check: Callable[[Request, Account], None]) -> None:
    REQUEST_CHECKS.append(check)


def account_of(request: Request) -> Account | None:
    return getattr(request.state, "account", None)


class SessionMiddleware:
    """Resolves the session cookie, sets the data scope for the request, and rejects cross-site writes."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        if request.method in UNSAFE_METHODS and not _same_origin(request):
            await JSONResponse(status_code=403, content={"detail": "跨站请求已拒绝"})(scope, receive, send)
            return
        token = request.cookies.get(COOKIE)
        account = await run_in_threadpool(_resolve, request.app.state.database, token) if token else None
        scope.setdefault("state", {})["account"] = account
        with scopes.scoped(scopes.user_scope(account.id, account.is_admin) if account else None):
            await self.app(scope, receive, send)


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        return True  # Browsers send Origin on cross-site writes; other clients carry no cookie risk.
    return urlsplit(origin).netloc == request.headers.get("host")


def _resolve(database, token: str) -> Account | None:
    with database.read() as session:
        account, stale = AccountService(AccountRepository(session)).resolve(token)
    if account is not None and stale:
        with database.transaction() as session:
            AccountService(AccountRepository(session)).refresh(token)
    return account


def guard(request: Request) -> None:
    route = request.scope.get("route")
    if route is None or route.path in PUBLIC_ROUTES:
        return
    account = account_of(request)
    if account is None:
        raise HTTPException(status_code=401, detail="请先登录")
    for check in REQUEST_CHECKS:
        check(request, account)
    parameters = {name: value for name, value in request.path_params.items() if name in OWNED_PARAMETERS}
    if parameters:
        with request.app.state.database.read() as session:
            repository = Repository(session)
            for name, value in parameters.items():
                repository.get(OWNED_PARAMETERS[name], value)


def require_admin(request: Request) -> None:
    account = account_of(request)
    if account is None or not account.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可用")


def require_roles(*roles: str):
    """A route dependency admitting only these roles."""
    def check(request: Request) -> None:
        account = account_of(request)
        if account is None or account.role not in roles:
            raise HTTPException(status_code=403, detail="当前账号不能使用此功能")
    return check
