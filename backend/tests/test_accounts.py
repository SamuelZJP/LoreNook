from backend.tests.state_fixtures import STATE_SCHEMA
import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.routing import APIRoute

from backend.api.access import CHAT_CHILD_PARAMETERS, OWNED_PARAMETERS, SELF_CHECKED_PARAMETERS
from backend.cli import run as run_cli
from backend.config import Settings
from backend.main import create_app
from backend.modules.accounts.service import AccountService
from backend.modules.accounts.throttle import LoginThrottle
from backend.modules.presence import HIGHEST, LOWEST, online_count
from backend.repository.accounts import AccountRepository
from backend.repository.models import Chat
from backend.repository.ownership import ScopeMissingError
from backend.repository.queries import Repository
from backend.shared.scope import SYSTEM, scoped
from backend.tests.conftest import TEST_PASSWORD, add_user, sign_in

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def run_app(database, scenario, **settings):
    app = create_app(Settings(database_url=database.engine.url.render_as_string(hide_password=False), **settings))

    async def main():
        async with app.router.lifespan_context(app):
            def client():
                return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test")
            await scenario(client)
    asyncio.run(main())


def test_sign_in_sign_out_and_public_routes(database):
    async def scenario(client):
        async with client() as anonymous:
            assert (await anonymous.get("/health")).status_code == 200
            home = (await anonymous.get("/api/public/home")).json()
            assert LOWEST <= home["online"] <= HIGHEST and home["icp_number"] == "测ICP备0号"
            assert (await anonymous.get("/api/chats")).status_code == 401
            assert (await anonymous.get("/api/auth/me")).status_code == 401
            assert (await anonymous.get("/openapi.json")).status_code == 404
            wrong = await anonymous.post("/api/auth/login", json={"username": "tester", "password": "wrong-password"})
            assert wrong.status_code == 401 and "lorenook_session" not in wrong.cookies
            unknown = await anonymous.post("/api/auth/login", json={"username": "nobody", "password": TEST_PASSWORD})
            assert unknown.status_code == 401 and unknown.json() == wrong.json()
        async with client() as browser:
            signed_in = await sign_in(browser)
            cookie = signed_in.headers["set-cookie"].lower()
            assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
            assert signed_in.json() == {"username": "tester", "role": "admin"}
            assert (await browser.get("/api/auth/me")).json() == {"username": "tester", "role": "admin"}
            assert (await browser.get("/api/chats")).status_code == 200
            assert (await browser.post("/api/auth/logout")).status_code == 204
            assert (await browser.get("/api/chats")).status_code == 401
    run_app(database, scenario, icp_number="测ICP备0号")


def test_cross_site_writes_are_rejected(database):
    async def scenario(client):
        async with client() as browser:
            await sign_in(browser)
            foreign = await browser.post("/api/user-identities", json={"name": "身份"},
                                         headers={"origin": "https://evil.example"})
            assert foreign.status_code == 403
            same = await browser.post("/api/user-identities", json={"name": "身份"}, headers={"origin": "https://test"})
            assert same.status_code == 201
    run_app(database, scenario)


def test_disabled_user_and_changed_password_end_sessions(database):
    add_user(database, "reader")

    async def scenario(client):
        async with client() as browser:
            await sign_in(browser, "reader")
            with database.transaction() as session:
                AccountService(AccountRepository(session)).set_disabled("reader", True)
            assert (await browser.get("/api/chats")).status_code == 401
            refused = await browser.post("/api/auth/login", json={"username": "reader", "password": TEST_PASSWORD})
            assert refused.status_code == 401
            with database.transaction() as session:
                AccountService(AccountRepository(session)).set_disabled("reader", False)
            await sign_in(browser, "reader")
            with database.transaction() as session:
                AccountService(AccountRepository(session)).set_password("reader", "another-password")
            assert (await browser.get("/api/chats")).status_code == 401
            await sign_in(browser, "reader", "another-password")
    run_app(database, scenario)


def test_sessions_expire_and_refresh(database):
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    with database.transaction() as session:
        token, _ = AccountService(AccountRepository(session), clock=lambda: now[0]).login("tester", TEST_PASSWORD)
    now[0] += timedelta(days=20)
    with database.read() as session:
        account, stale = AccountService(AccountRepository(session), clock=lambda: now[0]).resolve(token)
    assert account.username == "tester" and stale
    with database.transaction() as session:
        AccountService(AccountRepository(session), clock=lambda: now[0]).refresh(token)
    now[0] += timedelta(days=29)
    with database.read() as session:
        assert AccountService(AccountRepository(session), clock=lambda: now[0]).resolve(token)[0] is not None
    now[0] += timedelta(days=2)
    with database.read() as session:
        assert AccountService(AccountRepository(session), clock=lambda: now[0]).resolve(token) == (None, False)


def test_login_throttle_waits_longer_after_repeated_failures():
    clock = [0.0]
    throttle = LoginThrottle(clock=lambda: clock[0])
    for _ in range(5):
        assert throttle.wait_seconds("user:a") == 0
        throttle.failed("user:a")
    assert throttle.wait_seconds("user:a") == 60 and throttle.wait_seconds("user:b") == 0
    clock[0] += 60
    throttle.failed("user:a")
    assert throttle.wait_seconds("user:a") == 120
    throttle.succeeded("user:a")
    assert throttle.wait_seconds("user:a") == 0


def test_login_api_answers_429_while_throttled(database):
    async def scenario(client):
        async with client() as browser:
            for _ in range(5):
                await browser.post("/api/auth/login", json={"username": "tester", "password": "wrong-password"})
            blocked = await browser.post("/api/auth/login", json={"username": "tester", "password": TEST_PASSWORD})
            assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
    run_app(database, scenario)


async def _owned_resources(browser) -> dict[str, str]:
    """One of each owned resource, created through the API; returns their URLs."""
    character = (await browser.post("/api/characters", json={
        "name": "角色", "state_schema": STATE_SCHEMA, "scenes": [{"name": "开场", "first_message": "第0楼"}]})).json()
    identity = (await browser.post("/api/user-identities", json={"name": "身份"})).json()
    chat = (await browser.post("/api/chats", json={"title": "聊天", "character_id": character["id"],
                                                   "user_identity_id": identity["id"]})).json()
    preset = (await browser.post("/api/writing-presets", json={"name": "预设", "source": "export default {}"})).json()
    model = (await browser.post("/api/model-configs", json={
        "name": "模型", "api_type": "openai", "base_url": "https://model.example/v1", "model": "m"})).json()
    await browser.post("/api/chat-templates", json={"name": "模板", "is_default": True})
    media = (await browser.post("/api/media", content=PNG)).json()
    return {
        "character": f"/api/characters/{character['id']}", "identity": f"/api/user-identities/{identity['id']}",
        "chat": f"/api/chats/{chat['id']}", "preset": f"/api/writing-presets/{preset['id']}",
        "model": f"/api/model-configs/{model['id']}",
        "media": media["url"], "character_card": f"/api/characters/{character['id']}/card",
        "chat_state": f"/api/chats/{chat['id']}/state", "chat_rounds": f"/api/chats/{chat['id']}/rounds",
        "chat_memory": f"/api/chats/{chat['id']}/memory", "chat_character": f"/api/chats/{chat['id']}/character",
        "chat_presets": f"/api/chats/{chat['id']}/writing-presets",
    }


def test_users_cannot_see_or_change_each_others_data(database):
    add_user(database, "neighbor")

    async def scenario(client):
        async with client() as owner, client() as neighbor:
            await sign_in(owner)
            await sign_in(neighbor, "neighbor")
            urls = await _owned_resources(owner)
            template_id = (await owner.get("/api/chat-templates")).json()[0]["id"]
            for name, url in urls.items():
                assert (await owner.get(url)).status_code == 200, name
                assert (await neighbor.get(url)).status_code == 404, name
            for url in ("/api/characters", "/api/user-identities", "/api/chats", "/api/writing-presets",
                        "/api/model-configs", "/api/chat-templates"):
                assert (await owner.get(url)).json() != [], url
                assert (await neighbor.get(url)).json() == [], url
            assert (await neighbor.patch(urls["character"], json={"name": "改"})).status_code == 404
            assert (await neighbor.patch(f"/api/chat-templates/{template_id}", json={"name": "改"})).status_code == 404
            assert (await neighbor.delete(f"/api/chat-templates/{template_id}")).status_code == 404
            assert (await neighbor.delete(urls["chat"])).status_code == 404
            assert (await neighbor.put(urls["chat_state"], json={"content": {}})).status_code == 404
            character_id = urls["character"].rsplit("/", 1)[1]
            identity_id = urls["identity"].rsplit("/", 1)[1]
            stolen = await neighbor.post("/api/chats", json={"title": "偷", "character_id": character_id,
                                                              "user_identity_id": identity_id})
            assert stolen.status_code == 404
            # Each user has their own default template.
            mine = await neighbor.post("/api/chat-templates", json={"name": "我的", "is_default": True})
            assert mine.status_code == 201
            # Uploading the same image gives the neighbor their own access to it.
            assert (await neighbor.post("/api/media", content=PNG)).status_code == 201
            assert (await neighbor.get(urls["media"])).status_code == 200
            assert (await owner.get(urls["chat"])).status_code == 200
    run_app(database, scenario)


def test_administrator_areas(database):
    add_user(database, "member")

    async def scenario(client):
        async with client() as admin, client() as member:
            await sign_in(admin)
            await sign_in(member, "member")
            assert (await admin.get("/api/admin/schema")).status_code == 200
            assert (await member.get("/api/admin/schema")).status_code == 403
            assert (await member.get("/api/admin/data")).status_code == 403
            assert (await admin.get("/api/image-workflows")).status_code == 200
            assert (await member.get("/api/image-workflows")).status_code == 403
            # The raw data view covers every user's rows, and new rows belong to the acting administrator.
            await member.post("/api/user-identities", json={"name": "成员的身份"})
            data = (await admin.get("/api/admin/data")).json()
            assert [row["name"] for row in data["tables"]["user_identities"]] == ["成员的身份"]
            created = await admin.post("/api/admin/data", json={"expected_revision": data["revision"], "operations": [
                {"action": "create", "table": "user_identities", "values": {"name": "管理员的身份"}}]})
            assert created.status_code == 200, created.text
            assert [row["name"] for row in (await admin.get("/api/user-identities")).json()] == ["管理员的身份"]
            assert [row["name"] for row in (await member.get("/api/user-identities")).json()] == ["成员的身份"]
    run_app(database, scenario)


def test_owned_rows_need_a_scope(database):
    with scoped(None):
        with pytest.raises(ScopeMissingError):
            with database.read() as session:
                Repository(session).list_chats()
        with pytest.raises(ScopeMissingError):
            with database.transaction() as session:
                session.add(Chat(title="无主"))
    with database.transaction() as session:
        chat = Repository(session).add(Chat(title="有主"))
    with scoped(SYSTEM), database.read() as session:
        assert Repository(session).get(Chat, chat.id).owner_id != ""


def test_every_path_parameter_is_checked(database):
    app = create_app(Settings(database_url=database.engine.url.render_as_string(hide_password=False)))
    known = set(OWNED_PARAMETERS) | CHAT_CHILD_PARAMETERS | SELF_CHECKED_PARAMETERS
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        names = set(route.param_convertors)
        assert names <= known, (route.path, names - known)
        if names & CHAT_CHILD_PARAMETERS:
            assert "chat_id" in names, route.path


def test_presence_follows_the_day_and_stays_steady():
    day = datetime(2026, 11, 25, tzinfo=UTC)  # A Wednesday
    at = lambda hour, minute=0: day + timedelta(hours=hour - 8, minutes=minute)  # Beijing time
    assert online_count(at(23)) > online_count(at(15)) > online_count(at(5))
    assert all(LOWEST <= online_count(day + timedelta(minutes=step * 7)) <= HIGHEST for step in range(500))
    assert abs(online_count(at(23, 0)) - online_count(at(23, 1))) <= 1


def test_command_line_user_administration(database):
    out = []
    run_cli(["user", "add", "writer"], database, read_password=lambda: "writer-password", out=out.append)
    run_cli(["user", "disable", "writer"], database, out=out.append)
    run_cli(["user", "list"], database, out=out.append)
    assert out[0] == "已创建 writer（user）" and "writer\tuser\t停用" in out
    with pytest.raises(ValueError):
        run_cli(["user", "add", "w"], database, read_password=lambda: "short", out=out.append)
