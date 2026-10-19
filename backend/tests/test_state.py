from backend.tests.state_fixtures import WORLD
from copy import deepcopy
import json
import sys
from pathlib import Path

import httpx
import pytest
from sqlalchemy import update

from backend.modules.state.patch import apply_operations
from backend.modules.state.prompts import render_update_prompt
from backend.modules.state.update import parse_patch_operations
from backend.modules.state.schema import python_initial_state, validate_state
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Character, Chat, ChatModelBinding, ModelConfig, Round, StateSnapshot, UserIdentity
from backend.repository.queries import Repository
from backend.shared.content import extract_content
from backend.shared.errors import ConflictError, StateInitializationError, StateSchemaError, StateUpdateError
from backend.tests.test_catalog_api import run_api
from backend.workflows.edit_state import replace_latest_state
from backend.workflows.state_update import run_state_update
from backend.llm.client import ModelClient

SCHEMA = '''
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict, field_validator

class World(BaseModel):
    日期: str = "2026-10-19"
    时间: str = "08:00"
    星期: str = "星期一"
    地点: str = ""

class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)
    世界: World = Field(default_factory=World)
    年龄: int = 16
    好感度: int = 0
    列表: list[str] = Field(default_factory=list)

    @field_validator("好感度")
    @classmethod
    def clamp(cls, value):
        return max(0, min(100, value))
'''


def patch_response(operations):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": "<UpdateVariable>\n<Analysis>时间及变量结算结论。</Analysis>\n<JSONPatch>" +
         json.dumps(operations, ensure_ascii=False) + "</JSONPatch>\n</UpdateVariable>"}
    ]}}]}


def test_state_prompt_preserves_embedded_placeholders_and_input():
    values = dict(user="名字{{ai_response}}", reference_info="参考{{user}}",
                  current_memory_yaml="变量: 1\n", recent_summaries="旧事件",
                  user_input='“啊，清月？”\n我有些难以置信\n{{reference_info}} ${example}',
                  ai_response="{{variable_update_rules}}", variable_update_rules="规则{{user}}")
    text = render_update_prompt(**values)
    for value in values.values():
        assert value in text
    assert "不要求用户报时" in text
    assert "不要据此更新变量" in text


def test_tagged_patch_parses_only_commands_not_brackets_in_assessment():
    text = ('<UpdateVariable>\n<Analysis>列表[0]不变；时间跨日。</Analysis>\n<JSONPatch>'
            '[{"op":"replace","path":"/世界/时间","value":"00:02"}]'
            '</JSONPatch>\n</UpdateVariable>')
    assert parse_patch_operations(text) == [{"op": "replace", "path": "/世界/时间", "value": "00:02"}]
    assert parse_patch_operations('<UpdateVariable><Analysis>无变化。</Analysis><JSONPatch>[]</JSONPatch></UpdateVariable>') == []


@pytest.mark.parametrize("text", [
    '[]',
    '<UpdateVariable><JSONPatch>[]</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis> </Analysis><JSONPatch>[]</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><JSONPatch>{}</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><JSONPatch>[NaN]</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><JSONPatch>[1e999]</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><JSONPatch>[</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><JSONPatch>[]</JSONPatch>',
    '<UpdateVariable><JSONPatch>[]</JSONPatch><Analysis>x</Analysis></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><Analysis>y</Analysis><JSONPatch>[]</JSONPatch></UpdateVariable>',
    '<UpdateVariable><Analysis>x</Analysis><JSONPatch>[]</JSONPatch><JSONPatch>[]</JSONPatch></UpdateVariable>',
    '```xml\n<UpdateVariable><Analysis>x</Analysis><JSONPatch>[]</JSONPatch></UpdateVariable>\n```',
])
def test_invalid_tagged_state_response_is_rejected(text):
    with pytest.raises(ValueError):
        parse_patch_operations(text)


def test_schema_defaults_nested_fields_corrections_and_module_cleanup():
    before = set(sys.modules)
    initial = python_initial_state(SCHEMA)
    assert initial == {"世界": {"日期": "2026-10-19", "时间": "08:00", "星期": "星期一", "地点": ""}, "年龄": 16, "好感度": 0, "列表": []}
    initial["列表"].append("一个")
    assert python_initial_state(SCHEMA)["列表"] == []
    result = validate_state(SCHEMA, {"世界": {"日期": "2026-10-20"}, "好感度": 999})
    assert result["好感度"] == 100 and result["世界"]["时间"] == "08:00"
    assert not any(name.startswith("lorenook_state_") for name in set(sys.modules) - before)
    assert validate_state("", {"世界": WORLD, "嵌套": [True, None, 4]}) == {"世界": WORLD, "嵌套": [True, None, 4]}


@pytest.mark.parametrize("source", ["not valid python ?", "Schema = 1", "class Schema: pass", "raise RuntimeError('失败')",
    "from pydantic import BaseModel\nclass Schema(BaseModel):\n    required: int"])
def test_invalid_schema_initialization_is_explicit(source):
    with pytest.raises(StateInitializationError):
        python_initial_state(source)
    assert not any(name.startswith("lorenook_state_") for name in sys.modules)


@pytest.mark.parametrize("value", [{"年龄": "不是数字"}, {"未知字段": 1}, {"好感度": float("nan")}, [], None])
def test_schema_validation_failure_does_not_mutate_input(value):
    original = deepcopy(value)
    with pytest.raises(StateSchemaError):
        validate_state(SCHEMA, value)
    if isinstance(value, dict) and "好感度" in value:
        assert str(value) == str(original)
    else:
        assert value == original


def test_patch_standard_array_insert_and_pointers_preserve_original():
    old = {"arr": ["a", "b"], "a/b": {"~key": 1}, "": "空键"}
    operations = [
        {"op": "add", "path": "/arr/1", "value": "inserted"},
        {"op": "add", "path": "/arr/-", "value": "last"},
        {"op": "replace", "path": "/a~1b/~0key", "value": 2},
        {"op": "replace", "path": "/", "value": "改空键"},
        {"op": "remove", "path": "/arr/0"},
    ]
    before = deepcopy((old, operations))
    result, skipped = apply_operations(old, operations)
    assert result == {"arr": ["inserted", "b", "last"], "a/b": {"~key": 2}, "": "改空键"}
    assert skipped == 0 and (old, operations) == before


@pytest.mark.parametrize("bad", [
    None, 3, [], {"op": []}, {"op": "move", "path": "/x"},
    {"op": "replace", "path": "/missing", "value": 1}, {"op": "add", "path": "/missing/x", "value": 1},
    {"op": "remove", "path": "/missing"}, {"op": "add", "path": "/x"},
    {"op": "add", "path": "bad", "value": 1}, {"op": "add", "path": "/bad~2", "value": 1},
    {"op": "replace", "path": "/arr/-", "value": 1}, {"op": "replace", "path": "/arr/01", "value": 1},
    {"op": "remove", "path": "/arr/-1"}, {"op": "add", "path": "/arr/4", "value": 1},
    {"op": "add", "path": "/arr/١", "value": 1}, {"op": "remove", "path": ""},
    {"op": "replace", "path": "", "value": []},
])
def test_invalid_patch_is_skipped_and_following_operation_runs(bad):
    value, skipped = apply_operations({"arr": [0], "x": 0}, [bad, {"op": "replace", "path": "/x", "value": 2}])
    assert value == {"arr": [0], "x": 2} and skipped == 1


def test_patch_root_object_and_escaped_token_order():
    result, skipped = apply_operations({"old": 1}, [
        {"op": "replace", "path": "", "value": {"~1": 1}},
        {"op": "replace", "path": "/~01", "value": 2},
    ])
    assert result == {"~1": 2} and skipped == 0


@pytest.mark.parametrize("text", ["无标签", "<content>未闭合", "</content><content>x", "<content> </content>",
    "<content>a</content><content>b</content>"])
def test_invalid_ai_content(text):
    with pytest.raises(StateUpdateError):
        extract_content(text)


def test_ai_content_exact_text():
    assert extract_content("<report_nya~>分析</report_nya~><content> 正文\r\n </content><other>x</other>") == " 正文\r\n "


@pytest.fixture
def state_round(database, chat):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        character = repo.get(Character, chat[1])
        character.state_schema = SCHEMA
        character.state_reference, character.state_update_rules = "参考设定", "限制好感度"
        repo.latest_state(character.id).content = python_initial_state(SCHEMA)
        model = repo.add(ModelConfig(chat_id=chat[0], name="状态模型", api_type="google_generate_content",
                                     base_url="https://provider.test/v1beta", api_key="state-key", model="test-model"))
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="state_update", model_config_id=model.id))
        record = repo.create_round(chat[0], " 用户输入\r\n", "<report_nya~>不得提供</report_nya~><content> 正文\r\n </content>")
        return chat[0], chat[1], record.id


def test_state_step_saves_snapshot_and_progress_atomically(database, state_round):
    chat_id, character_id, round_id = state_round
    calls = []
    def handler(request):
        assert database.engine.pool.checkedout() == 0
        calls.append(request)
        body = json.loads(request.content)
        text = body["contents"][0]["parts"][0]["text"]
        assert "参考设定" in text and "限制好感度" in text
        assert "用户输入\r\n" in text and " 正文\r\n " in text and "不得提供" not in text
        assert "好感度: 0" in text and "身份" in text
        assert body["generationConfig"]["responseMimeType"] == "text/plain"
        headings = ["## 特别强调", "## 上下文", "## 过去状态", "## 最近剧情回顾",
                    "## 本回合对话", "## 变量更新规则", "## 世界状态约定", "## 输出格式"]
        assert [text.index(heading) for heading in headings] == sorted(text.index(heading) for heading in headings)
        assert "<Reference_Info>\n参考设定\n</Reference_Info>" in text
        assert "<Variable_Update_Rules>\n限制好感度\n</Variable_Update_Rules>" in text
        return httpx.Response(200, json=patch_response([
            {"op": "replace", "path": "/好感度", "value": 150},
            {"op": "replace", "path": "/不存在", "value": 1},
            {"op": "add", "path": "/列表/0", "value": "新增"},
        ]))
    async def scenario(client):
        path = f"/api/chats/{chat_id}/rounds/{round_id}/state-update"
        result = await client.post(path)
        assert result.status_code == 200, result.text
        assert result.json()["archive_step"] == "round_summary" and result.json()["skipped_operations"] == 1
        assert result.json()["state"]["content"]["好感度"] == 100
        assert result.json()["state"]["content"]["列表"] == ["新增"]
        assert (await client.post(path)).status_code == 409
        assert (await client.get(f"/api/chats/{chat_id}/state")).json() == result.json()["state"]
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 1
    with database.read() as session:
        repo = Repository(session)
        assert repo.get(Round, round_id).archive_step == "round_summary"
        assert repo.get(Round, round_id).archive_error is None
        assert repo.latest_state(character_id).round_id == round_id


@pytest.mark.parametrize("operations,skipped", [([], 0), ([{"op": "replace", "path": "/missing", "value": 1}], 1)])
def test_empty_or_all_skipped_patch_can_save_unchanged_state(database, state_round, operations, skipped):
    chat_id, character_id, round_id = state_round
    async def scenario(client):
        result = await client.post(f"/api/chats/{chat_id}/rounds/{round_id}/state-update")
        assert result.status_code == 200, result.text
        assert result.json()["skipped_operations"] == skipped
        assert result.json()["state"]["content"] == python_initial_state(SCHEMA)
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: httpx.Response(200, json=patch_response(operations))))


@pytest.mark.parametrize("failure,status", [("model", 502), ("json", 422), ("candidate", 422),
    ("schema", 422), ("bad_part", 422), ("content", 422)])
def test_update_failure_keeps_old_state_and_records_retry_error(database, state_round, failure, status):
    chat_id, character_id, round_id = state_round
    if failure == "content":
        with database.transaction() as session:
            Repository(session).get(Round, round_id).ai_output = "缺少正文标签"
    calls = []
    def handler(request):
        calls.append(request)
        if failure == "model":
            return httpx.Response(429, json={"error": "state-key"})
        if failure == "json":
            value = patch_response([])
            value["candidates"][0]["content"]["parts"][0]["text"] = "not-json"
        elif failure == "candidate":
            value = {"candidates": []}
        elif failure == "bad_part":
            value = {"candidates": [{"finishReason": "STOP", "content": {"parts": [1]}}]}
        else:
            value = patch_response([{"op": "replace", "path": "/年龄", "value": "bad"}])
        return httpx.Response(200, json=value)
    async def scenario(client):
        response = await client.post(f"/api/chats/{chat_id}/rounds/{round_id}/state-update")
        assert response.status_code == status, response.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == (0 if failure == "content" else 1)
    with database.read() as session:
        repo = Repository(session)
        assert repo.latest_state(character_id).round_id is None
        assert repo.get(Round, round_id).archive_step == "state_update"
        assert repo.get(Round, round_id).archive_error and "state-key" not in repo.get(Round, round_id).archive_error


def test_stale_generation_does_not_overwrite_newer_input(database, state_round):
    chat_id, character_id, round_id = state_round
    def handler(request):
        with database.transaction() as session:
            Repository(session).latest_state(character_id).content = python_initial_state(SCHEMA) | {"好感度": 9}
        return httpx.Response(200, json=patch_response([{"op": "replace", "path": "/好感度", "value": 5}]))
    async def scenario(client):
        response = await client.post(f"/api/chats/{chat_id}/rounds/{round_id}/state-update")
        assert response.status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        repo = Repository(session)
        assert repo.latest_state(character_id).content["好感度"] == 9
        assert repo.get(Round, round_id).archive_step == "state_update"


def test_default_app_creates_schema_state_and_edits_initial_snapshot(database):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "用户"})).json()
        created = await client.post("/api/chats", json={"title": "聊天", "character_id": character["id"], "user_identity_id": identity["id"]})
        assert created.status_code == 201, created.text
        chat_id = created.json()["id"]
        assert created.json()["latest_state"]["content"] == python_initial_state(SCHEMA)
        path = f"/api/chats/{chat_id}/state"
        edited = await client.put(path, json={"content": {"好感度": -3}})
        assert edited.status_code == 200 and edited.json()["content"]["好感度"] == 0
        assert edited.json()["id"] == created.json()["latest_state"]["id"]
        invalid = await client.put(path, json={"content": {"年龄": "bad"}})
        assert invalid.status_code == 422
        assert (await client.get(path)).json() == edited.json()
        assert (await client.get("/api/chats/missing/state")).status_code == 404
    run_api(database, scenario)


def test_manual_edit_blocks_pending_archive_then_updates_latest_completed_state(database, state_round):
    chat_id, character_id, round_id = state_round
    async def scenario(client):
        path = f"/api/chats/{chat_id}/state"
        assert (await client.put(path, json={"content": {}})).status_code == 409
        with database.transaction() as session:
            repo = ArchiveRepository(session)
            repo.save_state(round_id, python_initial_state(SCHEMA))
            repo.save_summary(round_id, "摘要")
            repo.save_decision(round_id)
        result = await client.put(path, json={"content": {"好感度": 500}})
        assert result.status_code == 200 and result.json()["content"]["好感度"] == 100
        assert result.json()["round_id"] == round_id
    run_api(database, scenario)


def test_manual_edit_detects_race_after_validation(database, chat):
    def validator(source, content):
        with database.transaction() as session:
            Repository(session).latest_state(chat[1]).content = {"竞争": True}
        return content
    with pytest.raises(ConflictError, match="状态或 Schema 已变化"):
        replace_latest_state(database, chat[0], {"世界": WORLD, "新状态": True}, validator=validator)
    with database.read() as session:
        assert Repository(session).latest_state(chat[1]).content == {"竞争": True}


def test_recent_summaries_include_episode_covered_rounds_and_retry_clears_error(database, state_round):
    chat_id, character_id, first_id = state_round
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_state(first_id, python_initial_state(SCHEMA))
        repo.save_summary(first_id, "摘要1")
        repo.save_decision(first_id)
        ids = [first_id]
        for number in range(2, 6):
            record = repo.create_round(chat_id, f"输入{number}", f"<content>正文{number}</content>")
            ids.append(record.id)
            repo.save_state(record.id, python_initial_state(SCHEMA) | {"年龄": 16 + number})
            repo.save_summary(record.id, f"摘要{number}")
            if number == 5:
                repo.save_decision(record.id, start_round_id=ids[0], end_round_id=ids[3])
                repo.save_episode(record.id, "情节汇总不用于状态更新")
            else:
                repo.save_decision(record.id)
        current_id = repo.create_round(chat_id, "输入6", "<content>正文6</content>").id
    calls = []
    def handler(request):
        calls.append(request)
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "第1回合：" not in prompt and "第2回合：" not in prompt
        assert prompt.index("第3回合：摘要3") < prompt.index("第4回合：摘要4") < prompt.index("第5回合：摘要5")
        assert "年龄: 21" in prompt and "情节汇总不用于" not in prompt
        return httpx.Response(429, json={}) if len(calls) == 1 else httpx.Response(200, json=patch_response([]))
    async def scenario(client):
        path = f"/api/chats/{chat_id}/rounds/{current_id}/state-update"
        assert (await client.post(path)).status_code == 502
        result = await client.post(path)
        assert result.status_code == 200 and result.json()["state"]["content"]["年龄"] == 21
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        repo = Repository(session)
        assert repo.get(Round, current_id).archive_error is None
        assert repo.latest_state(character_id).round_id == current_id


def test_state_update_scope_and_missing_binding_fail_before_model(database, state_round):
    chat_id, character_id, round_id = state_round
    with database.transaction() as session:
        repo = Repository(session)
        other = repo.add(Chat(title="另一个聊天")).id
        repo.add(Character(chat_id=other, name="其他角色"))
        repo.add(UserIdentity(chat_id=other, name="其他身份"))
        repo.delete(repo.model_binding(chat_id, "state_update"))
    calls = []
    async def scenario(client):
        assert (await client.post(f"/api/chats/{other}/rounds/{round_id}/state-update")).status_code == 404
        assert (await client.post(f"/api/chats/{chat_id}/rounds/{round_id}/state-update")).status_code == 409
        assert (await client.post(f"/api/chats/{chat_id}/rounds/missing/state-update")).status_code == 404
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == []


def test_state_save_failure_rolls_back_snapshot_and_step(database, state_round, monkeypatch):
    chat_id, character_id, round_id = state_round
    original = ArchiveRepository.save_state
    def fail_after_save(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("保存后提交前失败")
    monkeypatch.setattr(ArchiveRepository, "save_state", fail_after_save)
    client = ModelClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=patch_response([]))))
    try:
        with pytest.raises(RuntimeError):
            run_state_update(database, client, chat_id, round_id)
    finally:
        client.close()
    with database.read() as session:
        repo = Repository(session)
        assert repo.latest_state(character_id).round_id is None
        assert repo.get(Round, round_id).archive_step == "state_update"


def test_invalid_unicode_state_is_rejected():
    with pytest.raises(StateSchemaError):
        validate_state("", {"value": "\ud800"})


def test_manual_edit_detects_json_type_change(database, chat):
    with database.transaction() as session:
        Repository(session).latest_state(chat[1]).content = {"值": 1}
    def validator(source, content):
        with database.transaction() as session:
            state = Repository(session).latest_state(chat[1])
            session.execute(update(StateSnapshot).where(StateSnapshot.id == state.id).values(content={"值": True}))
        return content
    with pytest.raises(ConflictError):
        replace_latest_state(database, chat[0], {"世界": WORLD, "值": 2}, validator=validator)


def test_manual_edit_persists_integer_to_boolean_change(database, chat):
    with database.transaction() as session:
        Repository(session).latest_state(chat[1]).content = {"值": 1}
    replace_latest_state(database, chat[0], {"世界": WORLD, "值": True})
    with database.read() as session:
        assert Repository(session).latest_state(chat[1]).content["值"] is True


def test_editable_schema_example():
    source = (Path(__file__).parents[1] / "modules/state/examples/basic.py").read_text(encoding="utf-8")
    assert python_initial_state(source)["世界"]["地点"] == "未知"
    result = validate_state(source, {"角色": {"好感度": 150, "关系": "恋人"}})
    assert result["角色"]["好感度"] == 100 and result["角色"]["关系"] == "恋人"
    assert validate_state(source, {"角色": {"好感度": -1, "关系": "恋人"}})["角色"]["关系"] == "朋友"
