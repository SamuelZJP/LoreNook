import pytest

from backend.modules.definitions.service import DefinitionService
from backend.repository.models import Character, StateSnapshot, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.catalog import DefinitionInput
from backend.tests.test_catalog_api import run_api


@pytest.mark.parametrize("scope", ["character", "identity", "chat_character", "chat_identity"])
def test_scoped_definition_api_crud_reorder_and_validation(database, chat, scope):
    with database.transaction() as session:
        repository = Repository(session)
        source_character = repository.add(Character(name="来源角色")).id
        source_identity = repository.add(UserIdentity(name="来源身份")).id
        other_character = repository.add(Character(name="另一个来源角色")).id
        chat_identity = repository.list_owned(UserIdentity, chat[0])[0].id
    paths = {
        "character": f"/api/characters/{source_character}/definitions",
        "identity": f"/api/user-identities/{source_identity}/definitions",
        "chat_character": f"/api/chats/{chat[0]}/character/definitions",
        "chat_identity": f"/api/chats/{chat[0]}/user-identity/definitions",
    }
    path = paths[scope]
    other_path = f"/api/characters/{other_character}/definitions"

    async def scenario(client):
        assert (await client.get(path)).json() == []
        first_response = await client.post(path, json={"content": "定义一", "order": 4})
        assert first_response.status_code == 201, first_response.text
        first = first_response.json()
        expected_owner = {"character": source_character, "identity": source_identity,
                          "chat_character": chat[1], "chat_identity": chat_identity}[scope]
        assert first["character_id" if scope.endswith("character") else "user_identity_id"] == expected_owner
        second = (await client.post(path, json={"content": "{{ invalid", "has_template": True,
                                               "enabled": False, "order": 8})).json()
        third = (await client.post(path, json={"content": "第三条", "order": 12})).json()
        foreign = (await client.post(other_path, json={"content": "其他归属定义"})).json()
        first_url = f"{path}/{first['id']}"
        assert (await client.get(first_url)).json() == first
        assert (await client.patch(first_url, json={})).json() == first
        patched = (await client.patch(first_url, json={"content": "新原文", "enabled": False})).json()
        assert patched["id"] == first["id"] and patched["order"] == 4 and patched["enabled"] is False
        for invalid in ({"content": None}, {"order": -1}, {"order": "2"}, {"enabled": "true"},
                        {"has_template": None}, {"character_id": other_character}, {"id": "custom-id"}):
            assert (await client.patch(first_url, json=invalid)).status_code == 422
        assert (await client.post(path, json={"content": "不能转移归属", "user_identity_id": source_identity})).status_code == 422
        for method, body in (("GET", None), ("PATCH", {"content": "应拒绝"}), ("DELETE", None)):
            response = await client.request(method, f"{path}/{foreign['id']}", **({"json": body} if body else {}))
            assert response.status_code == 404
        for ids, expected in (([first["id"], first["id"], second["id"]], 422),
                              ([first["id"]], 409), ([first["id"], second["id"], foreign["id"]], 409)):
            result = await client.put(path + "/reorder", json={"definition_ids": ids})
            assert result.status_code == expected
        assert [item["order"] for item in (await client.get(path)).json()] == [4, 8, 12]
        ordered_ids = [third["id"], second["id"], first["id"]]
        response = await client.put(path + "/reorder", json={"definition_ids": ordered_ids})
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()] == ordered_ids
        assert [item["order"] for item in response.json()] == [0, 1, 2]
        assert (await client.delete(first_url)).status_code == 204
        assert (await client.get(first_url)).status_code == 404
        assert len((await client.get(path)).json()) == 2
    run_api(database, scenario)


def test_library_definition_routes_cannot_access_chat_copies(database, chat):
    with database.transaction() as session:
        repository = Repository(session)
        definition = DefinitionService(repository, character_id=chat[1], chat_id=chat[0]).create(
            DefinitionInput(content="聊天副本")
        )
    async def scenario(client):
        source_path = f"/api/characters/{chat[1]}/definitions"
        assert (await client.get(source_path)).status_code == 404
        assert (await client.patch(f"{source_path}/{definition.id}", json={"content": "错误归属"})).status_code == 404
        assert (await client.get("/api/characters/missing/definitions")).status_code == 404
        assert (await client.get("/api/chats/missing/character/definitions")).status_code == 404
    run_api(database, scenario)


def test_resolve_http_returns_both_groups_or_one_identified_error(database, chat):
    with database.transaction() as session:
        repository = Repository(session)
        character_service = DefinitionService(repository, character_id=chat[1], chat_id=chat[0])
        character = character_service.create(DefinitionInput(content="{{ state['年龄'] }}", has_template=True))
        character_service.create(DefinitionInput(content="{{ ignored }}", has_template=True, enabled=False))
        identity_id = repository.list_owned(UserIdentity, chat[0])[0].id
        user = DefinitionService(repository, user_identity_id=identity_id, chat_id=chat[0]).create(
            DefinitionInput(content="{{ state['世界']['日期'] }}", has_template=True)
        )
    async def scenario(client):
        path = f"/api/chats/{chat[0]}/definitions/resolve"
        response = await client.post(path)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["chat_id"] == chat[0] and result["state_snapshot_id"]
        assert result["character_definitions"] == [{"id": character.id, "order": 0, "content": "16"}]
        assert result["user_definitions"] == [{"id": user.id, "order": 0, "content": "2026-10-19"}]
        definition_url = f"/api/chats/{chat[0]}/user-identity/definitions/{user.id}"
        assert (await client.patch(definition_url, json={"content": "first\n{{ state['missing'] }}"})).status_code == 200
        failed = await client.post(path)
        assert failed.status_code == 422
        assert failed.json()["detail"]["definition_id"] == user.id
        assert failed.json()["detail"]["line"] == 2
        assert "character_definitions" not in failed.json()
        assert (await client.get(definition_url)).json()["content"] == "first\n{{ state['missing'] }}"
        assert (await client.patch(definition_url, json={"enabled": False})).status_code == 200
        assert (await client.post(path)).json()["user_definitions"] == []
        assert (await client.post("/api/chats/missing/definitions/resolve")).status_code == 404
    run_api(database, scenario)


def test_resolve_http_reports_missing_state(database, chat):
    with database.transaction() as session:
        repository = Repository(session)
        snapshot = repository.latest_state(chat[1])
        repository.delete(snapshot)
    async def scenario(client):
        result = await client.post(f"/api/chats/{chat[0]}/definitions/resolve")
        assert result.status_code == 409
    run_api(database, scenario)
