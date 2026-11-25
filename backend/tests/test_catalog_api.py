from backend.tests.conftest import sign_in
from backend.tests.state_fixtures import WORLD, STATE_SCHEMA
import asyncio

import httpx
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.modules.state.schema import python_initial_state
from backend.repository.models import Chat, Round
from backend.repository.queries import Repository


def run_api(database, scenario, factory=python_initial_state, llm_transport=None):
    app = create_app(Settings(api_docs=True, database_url=database.engine.url.render_as_string(hide_password=False)), factory,
                     llm_transport=llm_transport)

    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
                await sign_in(client)
                await scenario(client)
    asyncio.run(run())


@pytest.mark.parametrize("path", ["/api/characters", "/api/user-identities"])
def test_library_crud_patch_semantics_and_validation(database, path):
    async def scenario(client):
        created = await client.post(path, json={"name": "来源", "avatar": "avatar.png", "portrait": "portrait.png", "description": "原描述",
                                               "definitions": [{"content": "定义原文"}], **({"state_schema": STATE_SCHEMA} if path == "/api/characters" else {})})
        assert created.status_code == 201, created.text
        data = created.json()
        assert data["chat_id"] is None and len(data["definitions"]) == 1
        url = f"{path}/{data['id']}"
        assert (await client.get(path)).json() == [data]
        assert (await client.get(url)).json() == data
        assert data["portrait"] == "portrait.png"
        patched = await client.patch(url, json={"name": "新名称", "avatar": None, "portrait": None})
        assert patched.status_code == 200
        assert patched.json()["name"] == "新名称" and patched.json()["avatar"] is None and patched.json()["portrait"] is None
        assert patched.json()["description"] == "原描述"
        assert patched.json()["definitions"] == data["definitions"]
        assert (await client.patch(url, json={})).json() == patched.json()
        for invalid in ({"name": None}, {"name": " \n"}, {"description": None}, {"definitions": None},
                        {"chat_id": "forbidden"}, {"definitions": [{"content": "定义", "order": -1}]},
                        {"definitions": [{"content": "定义", "enabled": "yes"}]}):
            assert (await client.patch(url, json=invalid)).status_code == 422
        assert (await client.patch(url, json={"definitions": []})).json()["definitions"] == []
        deleted = await client.delete(url)
        assert deleted.status_code == 204 and deleted.content == b""
        assert (await client.get(url)).status_code == 404
        assert (await client.delete(url)).status_code == 404
        assert (await client.get(path)).json() == []
    run_api(database, scenario)


def test_chat_endpoints_default_state_and_copy_scoping(database):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA,
                                    "scenes": [{"name": "开场", "first_message": "第0楼"}],
                                    "definitions": [{"content": "设定"}]})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        created = await client.post("/api/chats", json={"title": "新聊天", "character_id": character["id"],
                                                       "user_identity_id": identity["id"]})
        assert created.status_code == 201, created.text
        data = created.json()
        url = f"/api/chats/{data['id']}"
        assert data["latest_state"]["content"] == {"世界": WORLD} and data["latest_state"]["round_id"] is None
        assert data["writing_preset_id"] is None and data["model_bindings"] == {}
        assert [chat["avatar"] for chat in (await client.get("/api/chats")).json()] == [None]
        assert (await client.get(url)).json() == data
        assert (await client.get(f"{url}/character")).json() == data["character"]
        assert (await client.get(f"{url}/user-identity")).json() == data["user_identity"]
        assert (await client.get(f"/api/characters/{data['character']['id']}")).status_code == 404
        assert (await client.delete(f"/api/user-identities/{data['user_identity']['id']}")).status_code == 404
        assert (await client.patch(f"{url}/character", json={"name": "副本", "scenes": [{"name": "开场", "first_message": "副本开场"}]})).status_code == 200
        assert (await client.patch(f"{url}/user-identity", json={"name": "副本身份"})).status_code == 200
        await client.patch(f"{url}/character", json={"avatar": "copy.png", "portrait": "cover.png"})
        assert [(chat["avatar"], chat["portrait"]) for chat in (await client.get("/api/chats")).json()] == [
            ("copy.png", "cover.png")]
        # Before any round, the list shows the opening's last line.
        assert [chat["last_line"] for chat in (await client.get("/api/chats")).json()] == ["副本开场"]
        with database.transaction() as session:
            session.add(Round(chat_id=data["id"], round_no=1, user_input="输入",
                              ai_output="<think>想法</think><content>第一行\n\n“走吧。”</content>"))
        assert [chat["last_line"] for chat in (await client.get("/api/chats")).json()] == ["“走吧。”"]
        assert (await client.get(f"/api/characters/{character['id']}")).json()["scenes"][0]["first_message"] == "第0楼"
        updated = (await client.patch(url, json={"title": "新标题", "recent_rounds": 0, "min_summaries": 0})).json()
        assert updated["title"] == "新标题" and updated["recent_rounds"] == 0
        assert (await client.get("/api/characters")).json() == [character]
        assert (await client.delete(url)).status_code == 204
        for suffix in ("", "/character", "/user-identity"):
            assert (await client.get(url + suffix)).status_code == 404
        assert (await client.get("/api/chats")).json() == []
    run_api(database, scenario)


def test_chat_creation_error_mapping_and_rollback(database):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA})).json()
        with database.transaction() as session:
            from backend.repository.models import Character
            Repository(session).get(Character, character["id"]).state_schema = "not empty"
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        payload = {"title": "新聊天", "character_id": character["id"], "user_identity_id": identity["id"]}
        response = await client.post("/api/chats", json=payload)
        assert response.status_code == 422 and "Schema" in response.json()["detail"]
        assert (await client.get("/api/chats")).json() == []
        assert (await client.post("/api/chats", json=payload | {"user_identity_id": "missing"})).status_code == 404
        for invalid in ({"recent_rounds": -1}, {"min_summaries": "2"}, {"title": " "},
                        {"model_bindings": {"unknown": "model"}}, {"initial_state": {}}, {"id": "custom-id"}):
            assert (await client.post("/api/chats", json=payload | invalid)).status_code == 422
        assert (await client.get("/api/chats")).json() == []
    run_api(database, scenario)


def test_state_factory_is_injected_into_http_workflow(database):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": "custom-schema"})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        response = await client.post("/api/chats", json={"title": "新聊天", "character_id": character["id"],
                                                        "user_identity_id": identity["id"]})
        assert response.status_code == 201, response.text
        assert response.json()["latest_state"]["content"] == {"世界": WORLD}
    def factory(source, overrides):
        assert source == "custom-schema" and overrides == {}
        return {"世界": dict(WORLD)}
    run_api(database, scenario, factory)


def test_incomplete_admin_data_returns_conflict(database):
    with database.transaction() as session:
        chat_id = Repository(session).add(Chat(title="不完整聊天")).id
    async def scenario(client):
        response = await client.get(f"/api/chats/{chat_id}")
        assert response.status_code == 409
    run_api(database, scenario)


def test_state_display_schema_carries_hints_and_tolerates_missing_schema(database):
    hinted = STATE_SCHEMA + '''
class Person(BaseModel):
    好感度: int = Field(50, json_schema_extra={"display": "bar", "max": 100})
class Schema(Schema):
    林: Person = Field(default_factory=Person)
'''

    async def scenario(client):
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()

        async def chat_with(source):
            character = (await client.post("/api/characters", json={"name": "角色", "state_schema": source,
                                        "scenes": [{"name": "开场", "first_message": "开场", "initial_state": {"世界": WORLD}}]})).json()
            chat = (await client.post("/api/chats", json={"title": "聊天", "character_id": character["id"],
                                                          "user_identity_id": identity["id"]})).json()
            return (await client.get(f"/api/chats/{chat['id']}/state/schema")).json()["json_schema"]

        schema = await chat_with(hinted)
        person = schema["$defs"]["Person"]["properties"]["好感度"]
        assert person["display"] == "bar" and person["max"] == 100
        assert await chat_with("") is None
    run_api(database, scenario, factory=python_initial_state)
