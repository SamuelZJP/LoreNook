import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from backend.cli import run as run_cli
from backend.config import Settings
from backend.demo.models import DemoPass
from backend.demo.passes import DemoPasses, Limits, status
from backend.demo.policy import ALLOWED
from backend.demo.sweeper import sweep
from backend.main import create_app
from backend.modules.accounts.service import AccountService
from backend.repository.accounts import AccountRepository
from backend.repository.models import (
    Character, Chat, ChatTemplate, LoginSession, MediaFile, ModelConfig, User, UserIdentity, WritingPreset,
)
from backend.repository.queries import Repository
from backend.shared.hooks import AppHooks
from backend.shared.scope import SYSTEM, scoped
from backend.tests.conftest import TEST_USERNAME, add_user, sign_in


@pytest.fixture
def template(database, chat):
    """The test administrator's account, with a library and the `chat` fixture's chat, serves as the template."""
    with database.transaction() as session:
        repository = Repository(session)
        character = repository.add(Character(name="模板角色", avatar="avatar.png"))
        identity = repository.add(UserIdentity(name="模板身份"))
        preset = repository.add(WritingPreset(name="模板预设", source="function build() {}"))
        model = repository.add(ModelConfig(name="模板模型", api_type="example", base_url="https://example.com",
                                           api_key="demo-key", model="m"))
        repository.add(MediaFile(name="avatar.png"))
        repository.add(ModelConfig(chat_id=chat[0], name="对话模型", api_type="example", base_url="https://example.com",
                                   model="m"))
        repository.add(ChatTemplate(name="默认", is_default=True, settings={
            "writing_preset_id": preset.id, "model_bindings": {"writing": model.id}}))
        return {"chat_id": chat[0], "character_id": character.id, "preset_id": preset.id, "model_id": model.id}


def link(database, **limits) -> str:
    with scoped(SYSTEM), database.transaction() as session:
        return DemoPasses(session).create("测试", Limits(**limits))[0]


def run_app(database, scenario):
    app = create_app(Settings(database_url=database.engine.url.render_as_string(hide_password=False),
                              demo_template=TEST_USERNAME), demo_sweeper=False)

    async def main():
        async with app.router.lifespan_context(app):
            def client():
                return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test")
            await scenario(client, app)
    asyncio.run(main())


def owned_count(database, model, owner_id):
    with scoped(SYSTEM), database.read() as session:
        return session.scalar(select(func.count()).select_from(model).where(model.owner_id == owner_id))


def test_redeeming_copies_the_template_once_and_signs_in_while_it_runs(database, template):
    token = link(database)
    with scoped(SYSTEM), database.read() as session:
        template_id = AccountRepository(session).user_by_name(TEST_USERNAME).id

    async def scenario(client, app):
        async with client() as visitor:
            redeemed = await visitor.post("/api/demo/redeem", json={"token": token})
            assert redeemed.status_code == 200
            assert "max-age=3600" in redeemed.headers["set-cookie"].lower() or \
                "max-age=3599" in redeemed.headers["set-cookie"].lower()
            me = (await visitor.get("/api/auth/me")).json()
            assert me["role"] == "demo"
            chats = (await visitor.get("/api/chats")).json()
            assert [c["id"] for c in chats] == [redeemed.json()["chat_id"]] != [template["chat_id"]]
            assert chats[0]["title"] == "测试聊天"
            templates = (await visitor.get("/api/chat-templates")).json()
            presets = {p["id"] for p in (await visitor.get("/api/writing-presets")).json()}
            models = (await visitor.get("/api/model-configs")).json()
            assert templates[0]["settings"]["writing_preset_id"] in presets - {template["preset_id"]}
            assert templates[0]["settings"]["model_bindings"]["writing"] == models[0]["id"] != template["model_id"]
            assert (await visitor.get("/api/media/avatar.png")).status_code != 403
            current = (await visitor.get("/api/demo/status")).json()
            assert current["rounds_left"] == 40 and current["images_left"] == 20
            await visitor.post(f"/api/chats/{chats[0]['id']}/writing", json={})
        async with client() as other_device:
            again = await other_device.post("/api/demo/redeem", json={"token": token})
            assert again.status_code == 200 and again.json() == redeemed.json()
            assert (await other_device.get("/api/auth/me")).json() == me
            assert (await other_device.get("/api/demo/status")).json() == current | {"rounds_left": 39}
        async with client() as other:
            assert (await other.post("/api/demo/redeem", json={"token": "nonsense"})).status_code == 410
            await sign_in(other)
            assert (await other.get("/api/demo/status")).status_code == 404

    run_app(database, scenario)
    with scoped(SYSTEM), database.read() as session:
        assert session.scalar(select(func.count()).select_from(User).where(User.role == "demo")) == 1
        demo = session.scalar(select(User).where(User.role == "demo"))
        record = DemoPasses(session).of_user(demo.id)
        assert status(record, datetime.now(UTC)) == "体验中"
        assert session.get(ModelConfig, template["model_id"]).owner_id == template_id
    for model in (Chat, Character, UserIdentity, WritingPreset, ModelConfig, ChatTemplate, MediaFile):
        assert owned_count(database, model, demo.id) == owned_count(database, model, template_id)


def test_demo_accounts_change_only_what_playing_needs(database, template):
    token = link(database, rounds=1)
    add_user(database, "reader")

    async def scenario(client, app):
        async with client() as visitor:
            chat_id = (await visitor.post("/api/demo/redeem", json={"token": token})).json()["chat_id"]
            config_id = (await visitor.get(f"/api/chats/{chat_id}/model-configs")).json()[0]["id"]
            assert (await visitor.post("/api/model-configs", json={})).status_code == 403
            assert (await visitor.patch(f"/api/chats/{chat_id}/model-configs/{config_id}",
                                        json={"base_url": "https://evil.example"})).status_code == 403
            assert (await visitor.post("/api/user-identities", json={"name": "新身份"})).status_code == 403
            assert (await visitor.patch(f"/api/chats/{chat_id}", json={"title": "改名"})).status_code == 200
            assert (await visitor.get(f"/api/chats/{chat_id}/illustrations")).status_code == 200
            assert (await visitor.post(f"/api/image-workflows", json={})).status_code == 403
            # The allowance is spent before the request body is checked.
            assert (await visitor.post(f"/api/chats/{chat_id}/writing", json={})).status_code == 422
            spent = await visitor.post(f"/api/chats/{chat_id}/writing", json={})
            assert spent.status_code == 429 and spent.json()["detail"] == "体验的写作次数已用完"
            assert (await visitor.get("/api/demo/status")).json()["rounds_left"] == 0
        async with client() as reader:
            await sign_in(reader, "reader")
            reader_chat = await reader.get("/api/chats")
            assert reader_chat.status_code == 200 and reader_chat.json() == []

    run_app(database, scenario)


def test_allowed_routes_exist():
    paths = create_app(Settings(database_url="sqlite:///:memory:")).openapi()["paths"]
    assert ALLOWED <= {(method.upper(), path) for path, operations in paths.items() for method in operations}


def test_unopened_and_revoked_links_do_not_redeem(database, template):
    stale = link(database, open_days=0)
    revoked = link(database)
    with scoped(SYSTEM), database.transaction() as session:
        passes = DemoPasses(session)
        for record in passes.all()[1:]:
            passes.revoke(record.id)
        assert [status(record, datetime.now(UTC)) for record in passes.all()] == ["已失效", "已失效"]

    async def scenario(client, app):
        async with client() as visitor:
            for token in (stale, revoked):
                assert (await visitor.post("/api/demo/redeem", json={"token": token})).status_code == 410

    run_app(database, scenario)


def test_finished_demos_are_signed_out_then_cleared(database, template):
    token = link(database)
    removed = []
    hooks = AppHooks(chat_deleted=[removed.append])

    async def scenario(client, app):
        async with client() as visitor:
            await visitor.post("/api/demo/redeem", json={"token": token})
            assert (await visitor.get("/api/chats")).status_code == 200
            with scoped(SYSTEM), database.transaction() as session:
                session.scalar(select(DemoPass)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
            ended = await visitor.get("/api/chats")
            assert ended.status_code == 401 and ended.json()["detail"] == "体验已结束"
            assert (await visitor.post("/api/demo/redeem", json={"token": token})).status_code == 410

    run_app(database, scenario)
    with scoped(SYSTEM), database.read() as session:
        demo = session.scalar(select(User).where(User.role == "demo"))
        template_chats = owned_count(database, Chat, session.scalar(select(User.id).where(User.role == "admin")))

    sweep(database, hooks)
    with scoped(SYSTEM), database.read() as session:
        assert session.get(User, demo.id).disabled
        assert session.scalar(select(func.count()).select_from(LoginSession)
                              .where(LoginSession.user_id == demo.id)) == 0
    assert owned_count(database, Chat, demo.id) == 1 and removed == []

    sweep(database, hooks, clock=lambda: datetime.now(UTC) + timedelta(hours=25))
    for model in (Chat, Character, UserIdentity, WritingPreset, ModelConfig, ChatTemplate, MediaFile):
        assert owned_count(database, model, demo.id) == 0
    assert len(removed) == 1 and owned_count(database, Chat, demo.id) == 0
    with scoped(SYSTEM), database.read() as session:
        assert session.scalar(select(DemoPass)).purged_at is not None
        assert owned_count(database, Chat, session.scalar(select(User.id).where(User.role == "admin"))) == template_chats


def test_demo_sessions_are_never_extended(database):
    user_id = add_user(database, "visitor", "demo")
    long_ago = datetime.now(UTC) - timedelta(days=2)
    with scoped(SYSTEM), database.transaction() as session:
        service = AccountService(AccountRepository(session), clock=lambda: long_ago)
        token = service.open_session(session.get(User, user_id), datetime.now(UTC) + timedelta(hours=1))
    with database.read() as session:
        account, stale = AccountService(AccountRepository(session)).resolve(token)
    assert account.role == "demo" and stale is False


def test_command_line_links(database):
    lines = []
    run_cli(["demo", "link", "--note", "某公司", "--rounds", "5"], database, out=lines.append,
            origin="https://example.com/")
    assert lines[0].startswith("https://example.com/try/") and "5 轮" in lines[1]
    pass_id = lines[1].split("\t")[0]
    lines.clear()
    run_cli(["demo", "list"], database, out=lines.append)
    assert "未打开" in lines[0] and "某公司" in lines[0]
    run_cli(["demo", "revoke", pass_id], database, out=lines.append)
    lines.clear()
    run_cli(["demo", "list"], database, out=lines.append)
    assert "已失效" in lines[0]
