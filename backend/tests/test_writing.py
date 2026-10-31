from pathlib import Path
import json

import httpx
import pytest
from sqlalchemy import select

from backend.modules.definitions.renderer import DefinitionRenderer
from backend.modules.presets.runtime import PresetRuntime
from backend.repository.archive import ArchiveRepository
from backend.repository.models import (
    Base, Character, Chat, ChatModelBinding, Definition, ModelConfig, StateSnapshot,
    UserIdentity, WritingPreset,
)
from backend.repository.queries import Repository
from backend.tests.test_catalog_api import run_api
from backend.tests.test_memory import seed_history
from backend.workflows.writing_materials import with_instruction

SOURCE = """
function build(m) {
    return {api_type: 'google_generate_content', body: {
        contents: [{role:'user', parts:[{text:JSON.stringify(m)}]}],
        generationConfig: {temperature:1}
    }};
}
function parse(r) {
    if (typeof r.text !== 'string') throw new Error('缺少回复文本');
    return r.text;
}
"""
EXAMPLE = (Path(__file__).parents[1] / "modules/presets/examples/google_tool.js").read_text(encoding="utf-8")
OUTPUT = "<report_nya~> 报告\r\n</report_nya~>\n<content> 正文\r\n </content>"


@pytest.fixture
def writing_chat(database, chat):
    with database.transaction() as session:
        repo = Repository(session)
        preset = repo.add(WritingPreset(chat_id=chat[0], name="写作", source=SOURCE))
        model = repo.add(ModelConfig(chat_id=chat[0], name="模型", api_type="google_generate_content",
                                    base_url="https://provider.test/v1beta", api_key="private-writing-key",
                                    model="example-model", default_parameters={"generationConfig": {"topP": 0.9}}))
        repo.get(Chat, chat[0]).writing_preset_id = preset.id
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="writing", model_config_id=model.id))
        repo.opening_scene(chat[1]).first_message = " 开场{{user}}\r\n"
        definition = repo.add(Definition(character_id=chat[1], order=2, has_template=True,
                                         content="年龄{{ state['年龄'] }}"))
        repo.add(Definition(character_id=chat[1], order=0, enabled=False, has_template=True, content="{{ missing }}"))
        identity = repo.list_owned(UserIdentity, chat[0])[0]
        repo.add(Definition(user_identity_id=identity.id, content=" 用户定义{{ Char }}\r\n"))
        state_id = repo.latest_state(chat[1]).id
        return {"chat_id": chat[0], "character_id": chat[1], "preset_id": preset.id,
                "model_config_id": model.id, "definition_id": definition.id, "state_snapshot_id": state_id}


def database_contents(database):
    with database.read() as session:
        return {table.name: [dict(row) for row in session.execute(
            select(table).order_by(*table.primary_key.columns)
        ).mappings()] for table in Base.metadata.tables.values()}


def tool_response(text):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"functionCall": {"name": "game_content", "args": {"content": text}}}
    ]}}]}


def test_generate_and_regenerate_return_unsaved_candidates(database, writing_chat):
    ids = writing_chat
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append(json.loads(body["contents"][0]["parts"][0]["text"]))
        assert body["generationConfig"] == {"topP": 0.9, "temperature": 1}
        assert request.headers["x-goog-api-key"] == "private-writing-key"
        return httpx.Response(200, json={"text": OUTPUT, "private_metadata": "不应回显"})
    before = database_contents(database)
    async def scenario(client):
        path = f"/api/chats/{ids['chat_id']}/writing"
        for text in (" 用户输入\r\n", " 编辑后的用户输入\n"):
            response = await client.post(path, json={"user_input": text})
            assert response.status_code == 200, response.text
            assert response.json() == {
                "chat_id": ids["chat_id"], "preset_id": ids["preset_id"],
                "model_config_id": ids["model_config_id"], "state_snapshot_id": ids["state_snapshot_id"],
                "based_on_round_id": None, "status": "awaiting_confirmation", "user_input": text,
                "ai_output": OUTPUT,
            }
            assert "private_metadata" not in response.text and "private-writing-key" not in response.text
        for invalid in ({}, {"user_input": None}, {"user_input": 3}, {"user_input": "输入", "round_id": "saved"},
                        {"user_input": "输入", "state": {}}, {"user_input": "输入", "ai_output": "替代回复"},
                        {"user_input": "输入", "preset_id": ids["preset_id"]}):
            assert (await client.post(path, json=invalid)).status_code == 422
        docs = (await client.get("/openapi.json")).json()
        operation = docs["paths"]["/api/chats/{chat_id}/writing"]["post"]
        assert operation["parameters"][0]["name"] == "chat_id"
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert database_contents(database) == before
    assert len(seen) == 2
    for value in seen:
        assert value["memory"] == "" and value["recent_rounds"] == []
        assert value["character_definitions"] == [{"id": ids["definition_id"], "order": 2, "content": "年龄16"}]
        assert value["user_definitions"][0]["content"] == " 用户定义角色\r\n"
        assert value["first_message"] == " 开场身份\r\n" and value["state"]["年龄"] == 16
    assert seen[0]["user_input"] != seen[1]["user_input"]


@pytest.mark.parametrize("case,status,expected_calls", [
    ("missing_chat", 404, 0), ("missing_preset", 409, 0), ("missing_model", 409, 0),
    ("missing_character", 409, 0), ("missing_identity", 409, 0), ("missing_state", 409, 0),
    ("definition", 422, 0), ("build", 422, 0), ("build_contract", 422, 0),
    ("incompatible", 422, 0), ("unsupported", 422, 0), ("bad_model", 422, 0),
    ("http", 502, 1), ("timeout", 504, 1), ("network", 502, 1), ("invalid_response", 502, 1),
    ("parse", 422, 1), ("empty_output", 422, 1),
])
def test_failure_stops_at_stage_and_never_writes(database, writing_chat, case, status, expected_calls):
    ids = writing_chat
    with database.transaction() as session:
        repo = Repository(session)
        if case == "missing_preset":
            repo.get(Chat, ids["chat_id"]).writing_preset_id = None
        elif case == "missing_model":
            repo.delete(repo.model_binding(ids["chat_id"], "writing"))
        elif case == "missing_character":
            repo.delete(repo.get(Character, ids["character_id"]))
        elif case == "missing_identity":
            repo.delete(repo.list_owned(UserIdentity, ids["chat_id"])[0])
        elif case == "missing_state":
            repo.delete(repo.get(StateSnapshot, ids["state_snapshot_id"]))
        elif case == "definition":
            repo.get(Definition, ids["definition_id"]).content = "{{ missing }}"
        elif case == "build":
            repo.get(WritingPreset, ids["preset_id"]).source = SOURCE.replace("function build(m) {", "function build(m) { throw new Error('build失败');")
        elif case == "build_contract":
            repo.get(WritingPreset, ids["preset_id"]).source = "function build(m){return [];} function parse(r){return 'ok';}"
        elif case == "incompatible":
            repo.get(ModelConfig, ids["model_config_id"]).api_type = "different"
        elif case == "unsupported":
            repo.get(ModelConfig, ids["model_config_id"]).api_type = "unsupported"
            repo.get(WritingPreset, ids["preset_id"]).source = SOURCE.replace("google_generate_content", "unsupported")
        elif case == "bad_model":
            repo.get(ModelConfig, ids["model_config_id"]).model = "../invalid"
        elif case == "parse":
            repo.get(WritingPreset, ids["preset_id"]).source = SOURCE.replace("return r.text;", "throw new Error('parse失败');")
    before = database_contents(database)
    calls = []
    def handler(request):
        calls.append(request)
        if case == "http":
            return httpx.Response(429, json={"error": "private-writing-key"})
        if case == "timeout":
            raise httpx.ReadTimeout("private-writing-key", request=request)
        if case == "network":
            raise httpx.ConnectError("private-writing-key", request=request)
        if case == "invalid_response":
            return httpx.Response(200, content=b"not-json")
        return httpx.Response(200, json={"text": " \n" if case == "empty_output" else OUTPUT})
    async def scenario(client):
        chat_id = "missing" if case == "missing_chat" else ids["chat_id"]
        response = await client.post(f"/api/chats/{chat_id}/writing", json={"user_input": "输入"})
        assert response.status_code == status, response.text
        assert "ai_output" not in response.json() and "private-writing-key" not in response.text
        if case == "definition":
            assert response.json()["detail"]["definition_id"] == ids["definition_id"]
        if case in {"build", "build_contract", "parse", "empty_output"}:
            assert response.json()["detail"]["stage"] == ("build" if case.startswith("build") else "parse")
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == expected_calls
    assert database_contents(database) == before


@pytest.mark.parametrize("step", ["state_update", "round_summary", "episode_decision", "episode_summary"])
def test_every_unfinished_archive_step_blocks_writing(database, writing_chat, step):
    ids = writing_chat
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        first = repo.create_round(ids["chat_id"], "已有输入", "<content>已有正文</content>")
        repo.save_state(first.id, {"年龄": 16})
        repo.save_summary(first.id, "已有摘要")
        repo.save_decision(first.id)
        current = repo.create_round(ids["chat_id"], "归档中", "<content>归档中</content>")
        if step != "state_update":
            repo.save_state(current.id, {"年龄": 17})
        if step in {"episode_decision", "episode_summary"}:
            repo.save_summary(current.id, "归档中摘要")
        if step == "episode_summary":
            repo.save_decision(current.id, start_round_id=first.id, end_round_id=first.id)
        repo.save_error(current.id, step, "归档失败待重试")
    before = database_contents(database)
    calls = []
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/writing", json={"user_input": "下一回合"})
        assert result.status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == [] and database_contents(database) == before


def test_complete_history_materials_and_current_input_not_in_total(database, writing_chat):
    ids = writing_chat
    round_ids = seed_history(database, ids["chat_id"])
    def handler(request):
        value = json.loads(json.loads(request.content)["contents"][0]["parts"][0]["text"])
        assert value["memory"].count("情节") == 2 and value["memory"].count("摘要") == 7
        assert [item["round_no"] for item in value["recent_rounds"]] == [16, 17, 18, 19, 20]
        assert value["user_input"] == "第21回合输入"
        assert value["recent_rounds"][-1]["id"] == round_ids[-1]
        assert value["state"]["序号"] == 20
        return httpx.Response(200, json={"text": OUTPUT})
    # The seeded state has no age field; adjust the template before the assertion snapshot.
    with database.transaction() as session:
        Repository(session).get(Definition, ids["definition_id"]).content = "序号{{ state['序号'] }}"
    before = database_contents(database)
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/writing", json={"user_input": "第21回合输入"})
        assert result.status_code == 200, result.text
        assert result.json()["based_on_round_id"] == round_ids[-1]
        assert result.json()["state_snapshot_id"] != ids["state_snapshot_id"]
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert database_contents(database) == before


def test_single_snapshot_and_same_preset_source_during_call(database, writing_chat, monkeypatch):
    ids = writing_chat
    # Rendering, both preset entry points and HTTP all happen after the read closes.
    original_resolve = DefinitionRenderer.resolve
    original_build, original_parse = PresetRuntime.build, PresetRuntime.parse
    def checked(original):
        def run(self, *args, **kwargs):
            assert database.engine.pool.checkedout() == 0
            return original(self, *args, **kwargs)
        return run
    monkeypatch.setattr(DefinitionRenderer, "resolve", checked(original_resolve))
    monkeypatch.setattr(PresetRuntime, "build", checked(original_build))
    monkeypatch.setattr(PresetRuntime, "parse", checked(original_parse))
    seen = []
    def handler(request):
        assert database.engine.pool.checkedout() == 0
        value = json.loads(json.loads(request.content)["contents"][0]["parts"][0]["text"])
        seen.append((value, request.headers["x-goog-api-key"], request.url.path))
        if len(seen) == 1:
            with database.transaction() as session:
                repo = Repository(session)
                repo.get(WritingPreset, ids["preset_id"]).source = SOURCE.replace("return r.text;", "return '新解析:' + r.text;")
                config = repo.get(ModelConfig, ids["model_config_id"])
                config.api_key, config.model = "updated-key", "updated-model"
                repo.get(StateSnapshot, ids["state_snapshot_id"]).content = {"年龄": 20}
                repo.get(Definition, ids["definition_id"]).content = "新定义{{ state['年龄'] }}"
                repo.opening_scene(ids["character_id"]).first_message = "新开场"
        return httpx.Response(200, json={"text": OUTPUT})
    async def scenario(client):
        path = f"/api/chats/{ids['chat_id']}/writing"
        first = await client.post(path, json={"user_input": "输入"})
        assert first.status_code == 200, first.text
        assert first.json()["ai_output"] == OUTPUT
        second = await client.post(path, json={"user_input": "重试"})
        assert second.json()["ai_output"] == "新解析:" + OUTPUT
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert seen[0][0]["state"]["年龄"] == 16 and seen[1][0]["state"]["年龄"] == 20
    assert seen[0][0]["character_definitions"][0]["content"] == "年龄16"
    assert seen[1][0]["character_definitions"][0]["content"] == "新定义20"
    assert seen[0][0]["first_message"] == " 开场身份\r\n" and seen[1][0]["first_message"] == "新开场"
    assert seen[0][1:] == ("private-writing-key", "/v1beta/models/example-model:generateContent")
    assert seen[1][1:] == ("updated-key", "/v1beta/models/updated-model:generateContent")
    with database.read() as session:
        assert Repository(session).rounds(ids["chat_id"]) == []


@pytest.mark.parametrize("valid", [True, False])
def test_real_example_end_to_end_tool_reply(database, writing_chat, valid):
    ids = writing_chat
    with database.transaction() as session:
        Repository(session).get(WritingPreset, ids["preset_id"]).source = EXAMPLE
    before = database_contents(database)
    calls = []
    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body["tools"][0]["functionDeclarations"][0]["name"] == "game_content"
        assert body["contents"][2]["parts"][0]["text"].endswith("\n<前缀> 用户输入\r\n<后缀>")
        assert "年龄16" in body["systemInstruction"]["parts"][0]["text"]
        return httpx.Response(200, json=tool_response(OUTPUT if valid else "<content>缺少报告</content>"))
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/writing", json={"user_input": " 用户输入\r\n"})
        assert result.status_code == (200 if valid else 422), result.text
        if valid:
            assert result.json()["ai_output"] == OUTPUT
        else:
            assert result.json()["detail"]["stage"] == "parse" and "ai_output" not in result.json()
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 1 and database_contents(database) == before


def test_retry_after_parse_failure_has_no_saved_candidate(database, writing_chat):
    ids = writing_chat
    calls = []
    before = database_contents(database)
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"text": " " if len(calls) == 1 else OUTPUT})
    async def scenario(client):
        path = f"/api/chats/{ids['chat_id']}/writing"
        failed = await client.post(path, json={"user_input": "同一输入"})
        assert failed.status_code == 422 and "ai_output" not in failed.json()
        retried = await client.post(path, json={"user_input": "同一输入"})
        assert retried.status_code == 200 and retried.json()["ai_output"] == OUTPUT
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2 and database_contents(database) == before


@pytest.mark.parametrize("user_input,instruction,expected", [
    ("ABCD", "abcd", "ABCD\n\n<instruction>\nabcd\n</instruction>"),
    (" 原文\r\n", " 指令\n", " 原文\r\n\n\n<instruction>\n指令\n</instruction>"),
    ("", "abcd", "<instruction>\nabcd\n</instruction>"),
    (" 原文\r\n", " \n", " 原文\r\n"),
    ("", "", ""),
])
def test_instruction_is_appended_to_the_request_input(user_input, instruction, expected):
    assert with_instruction(user_input, instruction) == expected
