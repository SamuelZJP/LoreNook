from copy import deepcopy

import httpx
import pytest

from backend.modules.state.initial import build_initial_state
from backend.modules.state.schema import checked_state, python_initial_state, validate_state
from backend.modules.state.world import validate_world
from backend.repository.models import Character, Round
from backend.repository.queries import Repository
from backend.shared.errors import StateInitializationError, StateSchemaError
from backend.tests.state_fixtures import STATE_SCHEMA, WORLD
from backend.tests.test_admin import apply, edit
from backend.tests.test_catalog_api import run_api
from backend.tests.test_state import SCHEMA, patch_response, state_round
from backend.tests.test_writing import database_contents


@pytest.mark.parametrize("field,value", [
    ("日期", "2024-02-29"), ("日期", "0001-01-01"), ("日期", "9999-12-31"),
    ("星期", "星期日"), ("星期", "星期六"), ("时间", "00:00"), ("时间", "23:59"),
    ("地点", ""), ("地点", " 任意地点\n"), ("天气", {"描述": "晴"}),
])
def test_valid_world_preserves_fields_and_does_not_require_weekday_agreement(field, value):
    content = {"世界": WORLD | {field: value}, "其他": [1, True, None]}
    before = deepcopy(content)
    assert validate_state("", content) == before
    assert content == before


@pytest.mark.parametrize("field,value", [
    ("日期", "2026-02-29"), ("日期", "2024-02-30"), ("日期", "0000-01-01"),
    ("日期", "2026-1-01"), ("日期", "20261019"), ("日期", "２０２６-１０-１９"),
    ("日期", "2026-10-19 星期一"), ("日期", "2026-10-19 "), ("日期", "第一天"),
    ("星期", "星期天"), ("星期", "周一"), ("星期", "星期七"), ("星期", "星期一 "),
    ("时间", "24:00"), ("时间", "23:60"), ("时间", "8:00"), ("时间", "08:00:00"),
    ("时间", "08:00Z"), ("时间", " 08:00"), ("时间", "０８:００"),
    ("地点", None), ("地点", 3), ("地点", []),
])
def test_invalid_world_fields_report_path(field, value):
    with pytest.raises(StateSchemaError, match=f"世界.{field}"):
        validate_state("", {"世界": WORLD | {field: value}})


@pytest.mark.parametrize("field", ["日期", "星期", "时间", "地点"])
def test_each_world_field_is_required(field):
    world = WORLD.copy()
    world.pop(field)
    with pytest.raises(ValueError, match=f"世界.{field}"):
        validate_world({"世界": world})


@pytest.mark.parametrize("content", [{}, {"世界": None}, {"世界": []}, {"世界": "世界"}])
def test_world_object_is_required(content):
    with pytest.raises(ValueError, match="世界"):
        validate_world(content)


def test_schema_and_injected_executors_cannot_bypass_world_contract():
    with pytest.raises(StateInitializationError):
        python_initial_state("")
    with pytest.raises(StateInitializationError, match="世界"):
        build_initial_state(lambda _: {}, "custom")
    with pytest.raises(StateSchemaError, match="世界"):
        checked_state(lambda *_: {}, "custom", {"世界": WORLD})
    with pytest.raises(StateSchemaError, match="世界"):
        validate_state("from pydantic import BaseModel\nclass Schema(BaseModel): pass", {"世界": WORLD})


def test_character_create_and_schema_edit_validate_defaults_atomically(database):
    async def scenario(client):
        for source in ("", "broken", SCHEMA.replace('"2026-10-19"', '"2026-02-30"')):
            result = await client.post("/api/characters", json={"name": "无效", "state_schema": source})
            assert result.status_code == 422, result.text
        assert (await client.get("/api/characters")).json() == []
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "用户"})).json()
        chat = (await client.post("/api/chats", json={"title": "聊天", "character_id": character["id"],
                                                     "user_identity_id": identity["id"]})).json()
        before = database_contents(database)
        for path in (f"/api/characters/{character['id']}", f"/api/chats/{chat['id']}/character"):
            result = await client.patch(path, json={"name": "不得保存", "state_schema": ""})
            assert result.status_code == 422, result.text
        assert database_contents(database) == before
        path = f"/api/chats/{chat['id']}/state"
        result = await client.put(path, json={"content": {"世界": WORLD | {"时间": "24:00"}}})
        assert result.status_code == 422 and "世界.时间" in result.text
        assert database_contents(database) == before
        # Saving a valid replacement schema does not recalculate existing snapshots.
        result = await client.patch(f"/api/chats/{chat['id']}/character",
                                    json={"state_schema": STATE_SCHEMA.replace("08:00", "09:00")})
        assert result.status_code == 200
        assert (await client.get(path)).json()["content"]["世界"]["时间"] == "08:00"
    run_api(database, scenario)


def test_invalid_model_world_patch_keeps_snapshot_and_step(database, state_round):
    chat_id, character_id, round_id = state_round
    before = database_contents(database)["state_snapshots"]
    async def scenario(client):
        result = await client.post(f"/api/chats/{chat_id}/rounds/{round_id}/state-update")
        assert result.status_code == 422 and "世界.日期" in result.text
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=patch_response([
        {"op": "replace", "path": "/世界/日期", "value": "2026-02-30"},
    ])))
    run_api(database, scenario, llm_transport=transport)
    assert database_contents(database)["state_snapshots"] == before
    with database.read() as session:
        record = Repository(session).get(Round, round_id)
        assert record.archive_step == "state_update" and record.archive_error


def test_admin_validates_written_world_but_reads_legacy_data_without_schema(database, chat):
    with database.transaction() as session:
        repo = Repository(session)
        state = repo.latest_state(chat[1])
        state_id = state.id
        state.content = {}  # Legacy data remains readable and does not block unrelated edits.
        repo.get(Character, chat[1]).state_schema = "must not execute"
    before = database_contents(database)
    async def scenario(client):
        snapshot = await client.get("/api/admin/data")
        assert snapshot.status_code == 200
        result = await apply(client, [edit("characters", chat[1], name="应回滚"),
                                      edit("state_snapshots", state_id, content={})])
        assert result.status_code == 422 and "世界" in result.text
        assert database_contents(database) == before
        assert (await apply(client, [edit("characters", chat[1], name="可编辑")])).status_code == 200
        result = await apply(client, [edit("state_snapshots", state_id, content={"世界": WORLD, "额外": True})])
        assert result.status_code == 200, result.text
    run_api(database, scenario)
