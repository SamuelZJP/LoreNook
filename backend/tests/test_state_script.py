import json
from pathlib import Path

import httpx
import pytest

from backend.modules.state.schema import python_initial_state
from backend.modules.state.script import run_state_script
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Character, Round
from backend.repository.queries import Repository
from backend.shared.errors import StateScriptError
from backend.tests.test_catalog_api import run_api
from backend.tests.test_state import SCHEMA, patch_response, state_round  # noqa: F401 (fixture)

RECORDING = '''
def process(state, previous, history):
    state["列表"] = [json.dumps({"previous": previous["年龄"], "history": [[h["round_no"], h["state"]["年龄"]] for h in history]})]
    state["年龄"] += 100
    return state
import json
'''


def configure(database, character_id, script, depth=0):
    with database.transaction() as session:
        character = Repository(session).get(Character, character_id)
        character.state_script, character.state_script_history = script, depth


def run_update(database, chat_id, round_id, operations, check, calls=None):
    def handler(request):
        if calls is not None:
            calls.append(request)
        return httpx.Response(200, json=patch_response(operations))
    async def scenario(client):
        await check(client, f"/api/chats/{chat_id}/rounds/{round_id}/state-update")
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


@pytest.fixture
def history_round(database, state_round):
    """Three archived rounds with 年龄 17, 18, 19 before the pending round at state_update."""
    chat_id, character_id, round_id = state_round
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        pending = repo.get(Round, round_id)
        session.delete(pending)
        session.flush()
        for age in (17, 18, 19):
            record = repo.create_round(chat_id, "输入", "<content>正文</content>")
            repo.save_state(record.id, python_initial_state(SCHEMA, {"年龄": age}))
            repo.save_summary(record.id, "摘要")
            repo.save_decision(record.id)
        record = repo.create_round(chat_id, "用户输入", "<content>正文</content>")
    return chat_id, character_id, record.id


@pytest.mark.parametrize("depth, history", [(0, []), (2, [[2, 18], [3, 19]]), (10, [[0, 16], [1, 17], [2, 18], [3, 19]])])
def test_script_gets_previous_and_history_and_changes_saved_state(database, history_round, depth, history):
    chat_id, character_id, round_id = history_round
    configure(database, character_id, RECORDING, depth)
    async def check(client, path):
        result = await client.post(path)
        assert result.status_code == 200, result.text
        content = result.json()["state"]["content"]
        assert content["年龄"] == 119 and content["好感度"] == 5
        assert json.loads(content["列表"][0]) == {"previous": 19, "history": history}
    run_update(database, chat_id, round_id, [{"op": "replace", "path": "/好感度", "value": 5}], check)


def test_failing_script_fails_step_and_retry_runs_again(database, state_round):
    chat_id, character_id, round_id = state_round
    configure(database, character_id, "def process(state, previous, history):\n    raise ValueError('年龄检查不通过')\n")
    calls = []
    async def check(client, path):
        result = await client.post(path)
        assert result.status_code == 422 and "年龄检查不通过" in result.json()["detail"]
        with database.read() as session:
            repo = Repository(session)
            record = repo.get(Round, round_id)
            assert record.archive_step == "state_update" and "状态脚本执行失败" in record.archive_error
            assert repo.state_for_round(chat_id, round_id) is None
        configure(database, character_id, "def process(state, previous, history):\n    return state\n")
        retry = await client.post(path)
        assert retry.status_code == 200, retry.text
        assert retry.json()["state"]["content"]["好感度"] == 5
    run_update(database, chat_id, round_id, [{"op": "replace", "path": "/好感度", "value": 5}], check, calls)
    assert len(calls) == 2


def test_unchanged_model_patch_fails_even_if_script_would_change(database, state_round):
    chat_id, character_id, round_id = state_round
    configure(database, character_id, "def process(state, previous, history):\n    state['好感度'] = 9\n    return state\n")
    async def check(client, path):
        result = await client.post(path)
        assert result.status_code == 422 and "完全相同" in result.json()["detail"]
    run_update(database, chat_id, round_id, [], check)


@pytest.mark.parametrize("script, message", [
    ("def process(state, previous, history):\n    state['年龄'] = 'x'\n    return state\n", "Schema"),
    ("def process(state, previous, history):\n    state['好感度'] = 500\n    return state\n", None),
    ("def process(state, previous, history):\n    return None\n", "必须返回状态对象"),
])
def test_script_output_goes_through_schema(database, state_round, script, message):
    chat_id, character_id, round_id = state_round
    configure(database, character_id, script)
    async def check(client, path):
        result = await client.post(path)
        if message is None:
            assert result.status_code == 200 and result.json()["state"]["content"]["好感度"] == 100
        else:
            assert result.status_code == 422 and message in result.json()["detail"]
    run_update(database, chat_id, round_id, [{"op": "replace", "path": "/好感度", "value": 5}], check)


def test_character_api_checks_script_on_save(database):
    async def scenario(client):
        bad = await client.post("/api/characters", json={"name": "角色", "state_schema": SCHEMA, "state_script": "x = 1"})
        assert bad.status_code == 422 and "process" in bad.json()["detail"]
        syntax = await client.post("/api/characters", json={"name": "角色", "state_schema": SCHEMA, "state_script": "def process(:"})
        assert syntax.status_code == 422
        too_deep = await client.post("/api/characters", json={"name": "角色", "state_schema": SCHEMA, "state_script_history": 101})
        assert too_deep.status_code == 422
        created = await client.post("/api/characters", json={
            "name": "角色", "state_schema": SCHEMA, "state_script": "def process(state, previous, history):\n    return state\n",
            "state_script_history": 3})
        assert created.status_code == 201, created.text
        assert created.json()["state_script_history"] == 3
        path = f"/api/characters/{created.json()['id']}"
        assert (await client.patch(path, json={"state_script": "process = 1"})).status_code == 422
        assert (await client.patch(path, json={"state_script": ""})).json()["state_script"] == ""
    run_api(database, scenario)


def test_empty_script_returns_state_unchanged():
    state = {"世界": {}}
    assert run_state_script("  ", state, {}, []) is state
    with pytest.raises(StateScriptError):
        run_state_script("def process(state, previous, history):\n    return {'x': float('nan')}\n", state, state, [])


def test_example_script_rolls_on_date_change_and_keeps_death(monkeypatch):
    source = (Path(__file__).parents[1] / "modules/state/examples/script.py").read_text(encoding="utf-8")
    alive = {"世界": {"日期": "2026-10-19"}, "角色": {"是否存活": True}}
    next_day = {"世界": {"日期": "2026-10-20"}, "角色": {"是否存活": True}}
    monkeypatch.setattr("random.random", lambda: 0.05)
    assert run_state_script(source, alive, alive, [])["角色"]["是否存活"] is True
    assert run_state_script(source, next_day, alive, [])["角色"]["是否存活"] is False
    monkeypatch.setattr("random.random", lambda: 0.5)
    assert run_state_script(source, next_day, alive, [])["角色"]["是否存活"] is True
    dead = {"世界": {"日期": "2026-10-19"}, "角色": {"是否存活": False}}
    assert run_state_script(source, next_day, dead, [])["角色"]["是否存活"] is False
