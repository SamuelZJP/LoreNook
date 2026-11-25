"""What a demo account may change. Reading is open; a write is refused unless its route is listed here.

The listed routes play a chat: write, confirm and archive rounds, edit state and episodes, draw. Everything
that defines the account (models, presets, workflows, characters, identities, uploads) stays as the template
made it. New routes are refused until listed.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, Request

from backend.api.access import UNSAFE_METHODS
from backend.demo.passes import DemoPasses, is_active
from backend.modules.accounts.service import Account
from backend.shared import scope as scopes

CHAT = "/api/chats/{chat_id}"
ROUND = CHAT + "/rounds/{round_id}"

ALLOWED: frozenset[tuple[str, str]] = frozenset({
    ("POST", "/api/chats"),
    ("PATCH", CHAT),
    ("DELETE", CHAT),
    ("POST", CHAT + "/writing"),
    ("POST", CHAT + "/writing-preview"),
    ("POST", CHAT + "/definitions/resolve"),
    ("POST", CHAT + "/archive"),
    ("PUT", CHAT + "/state"),
    ("PUT", CHAT + "/episodes/{episode_id}"),
    ("POST", ROUND + "/archive/retry"),
    ("POST", ROUND + "/state-update"),
    ("POST", ROUND + "/round-summary"),
    ("PUT", ROUND + "/summary"),
    ("POST", ROUND + "/episode-decision"),
    ("POST", ROUND + "/episode-summary"),
    ("POST", CHAT + "/recall"),
    ("PUT", CHAT + "/recall-settings"),
    ("POST", CHAT + "/recall-setup"),
    ("PUT", CHAT + "/illustration-settings"),
    ("POST", CHAT + "/illustration-setup"),
    ("POST", ROUND + "/illustrations"),
    ("POST", ROUND + "/illustration-prompt"),
    ("PATCH", CHAT + "/illustrations/{illustration_id}"),
})

# Writes that use up the demo's allowance: route → (used column, limit column, message).
COUNTED = {
    ("POST", CHAT + "/writing"): ("rounds_used", "rounds_limit", "体验的写作次数已用完"),
    # Drawn on request. Automatic drawing follows archived rounds, so the round allowance bounds it.
    ("POST", ROUND + "/illustrations"): ("images_used", "images_limit", "体验的生图次数已用完"),
}


def check_demo_request(request: Request, account: Account) -> None:
    if account.role != "demo":
        return
    method, route = request.method, request.scope["route"].path
    database = request.app.state.database
    with scopes.scoped(scopes.SYSTEM):
        with database.read() as session:
            record = DemoPasses(session).of_user(account.id)
            active = is_active(record, datetime.now(UTC))
        if not active:
            raise HTTPException(status_code=401, detail="体验已结束")
        if method not in UNSAFE_METHODS:
            return
        if (method, route) not in ALLOWED:
            raise HTTPException(status_code=403, detail="体验账号不能进行这项操作")
        counted = COUNTED.get((method, route))
        if counted is not None:
            used, limit, message = counted
            with database.transaction() as session:
                record = DemoPasses(session).of_user(account.id)
                if getattr(record, used) >= getattr(record, limit):
                    raise HTTPException(status_code=429, detail=message)
                setattr(record, used, getattr(record, used) + 1)
