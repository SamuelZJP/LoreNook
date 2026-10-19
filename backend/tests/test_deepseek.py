from copy import deepcopy
import json

import httpx
import pytest

from backend.llm.client import ModelClient
from backend.llm.generation import text_request
from backend.llm.text import deepseek_response_text
from backend.repository.models import ModelConfig
from backend.repository.queries import Repository
from backend.schemas.archive import ArchiveConfirm
from backend.schemas.presets import BuiltRequest
from backend.shared.errors import ArchiveExecutionError, ModelConfigurationError
from backend.tests.test_archive_workflow import archive_chat, seed_history, payload
from backend.tests.test_models import connection
from backend.workflows.archive import confirm_archive, retry_archive

API = "deepseek_chat_completions"
DEFAULTS = {"temperature": 0.2, "max_tokens": 4096, "stream": False, "thinking": {"type": "disabled"}}


def reply(text):
    return {"id": "test-reply", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": text, "reasoning_content": "不作为正文"}}],
            "usage": {"total_tokens": 120}, "provider_extra": {"retained": True}}


def test_native_transport_exact_log_defaults_auth_and_full_reply(tmp_path):
    seen = []
    response = reply(" 完整输出\r\n")
    response["choices"].append(deepcopy(response["choices"][0]))  # transport preserves every candidate
    def handler(request):
        seen.append(request)
        assert str(request.url) == "https://provider.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer private-test-key"
        assert "x-goog-api-key" not in request.headers
        assert json.loads(request.content) == {**DEFAULTS, "temperature": 0, "model": "override",
            "messages": [{"role": "system", "content": " 系统\r\n"}, {"role": "user", "content": " 用户\n"}]}
        return httpx.Response(200, json=response)
    config = connection(api_type=API, base_url="https://provider.test/v1/", model="deepseek-flash",
                        default_parameters=DEFAULTS)
    request = BuiltRequest(api_type=API, body={"temperature": 0, "model": "override", "messages": [
        {"role": "system", "content": " 系统\r\n"}, {"role": "user", "content": " 用户\n"}]})
    before = deepcopy((config.model_dump(), request.model_dump()))
    client = ModelClient(transport=httpx.MockTransport(handler), recording_directory=tmp_path)
    try:
        assert client.invoke(config, request).response == response
    finally:
        client.close()
    assert (config.model_dump(), request.model_dump()) == before
    assert len(seen) == 1
    assert (tmp_path / "000001/request.json").read_bytes() == seen[0].content
    assert json.loads((tmp_path / "000001/response.raw").read_bytes()) == response
    meta = json.loads((tmp_path / "000001/metadata.json").read_text(encoding="utf-8"))
    assert meta["model"] == "override" and meta["api_type"] == API
    assert "private-test-key" not in "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file())


@pytest.mark.parametrize("body,config_values", [
    ({}, {}), ({"messages": []}, {}), ({"messages": "bad"}, {}),
    ({"messages": [{}], "stream": True}, {}), ({"messages": [{}], "stream": 1}, {}),
    ({"messages": [{}], "model": None}, {}), ({"messages": [{}], "model": " "}, {}),
    ({"messages": [{}]}, {"api_key": "bad\nkey"}),
    ({"messages": [{}]}, {"base_url": "http://provider.test?key=secret"}),
])
def test_invalid_deepseek_requests_never_send(body, config_values):
    def handler(request):
        pytest.fail("Invalid requests must not reach transport")
    client = ModelClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ModelConfigurationError):
            client.invoke(connection(api_type=API, **config_values), BuiltRequest(api_type=API, body=body))
    finally:
        client.close()


@pytest.mark.parametrize("choice", [None, {}, {"finish_reason": "length"},
    {"finish_reason": "stop", "message": {"role": "assistant", "content": ""}},
    {"finish_reason": "stop", "message": {"role": "assistant", "content": None}},
    {"finish_reason": "stop", "message": {"role": "assistant", "content": "x", "tool_calls": [{}]}},
    {"finish_reason": "stop", "message": {"role": "assistant", "content": "x", "function_call": {"name": "x"}}},
    {"finish_reason": "stop", "message": {"role": "assistant", "content": "x", "refusal": "refused"}},
    {"finish_reason": "stop", "message": {"role": "user", "content": "x"}},
])
def test_invalid_deepseek_content_rejected(choice):
    with pytest.raises(ValueError):
        deepseek_response_text({"choices": [choice]})


def test_visible_text_keeps_whitespace_and_ignores_reasoning():
    assert deepseek_response_text(reply(" 正文\r\n")) == " 正文\r\n"
    for choices in ([], reply("x")["choices"] * 2):
        with pytest.raises(ValueError):
            deepseek_response_text({"choices": choices})


def test_native_request_keeps_same_system_user_text_as_google():
    google = text_request("google_generate_content", "系统\r\n", "用户\n")
    deepseek = text_request(API, "系统\r\n", "用户\n")
    assert deepseek.body["messages"][0]["content"] == google.body["systemInstruction"]["parts"][0]["text"]
    assert deepseek.body["messages"][1]["content"] == google.body["contents"][0]["parts"][0]["text"]
    assert deepseek.body["response_format"] == {"type": "text"}
    assert deepseek.body["stream"] is False


@pytest.mark.parametrize("failed_step", [None, "state_update", "round_summary", "episode_summary"])
def test_full_deepseek_archive_and_retry_records(database, archive_chat, tmp_path, failed_step):
    previous = seed_history(database, archive_chat)
    with database.transaction() as session:
        repo = Repository(session)
        model = repo.list_owned(ModelConfig, archive_chat)[0]
        model.api_type, model.base_url, model.model = API, "https://provider.test/v1", "deepseek-flash"
        model.default_parameters = DEFAULTS
    calls = []
    failed = False
    def handler(request):
        nonlocal failed
        assert database.engine.pool.checkedout() == 0
        body = json.loads(request.content)
        assert body["model"] == "deepseek-flash" and body["thinking"] == {"type": "disabled"}
        assert not {"contents", "systemInstruction", "generationConfig"}.intersection(body)
        system = body["messages"][0]["content"]
        step = "state_update" if "JSON Patch" in system else "episode_summary" if "连续回合" in system else "round_summary"
        calls.append(step)
        if step == failed_step and not failed:
            failed = True
            return httpx.Response(429, json={"error": {"message": "upstream error"}})
        if step == "state_update":
            text = '<UpdateVariable><Analysis>跨日结算。</Analysis><JSONPatch>[{"op":"replace","path":"/世界/日期","value":"2026-10-20"}]</JSONPatch></UpdateVariable>'
        else:
            text = " 2026/10/20 回合摘要\r\n" if step == "round_summary" else " 2026/10/19 用户与角色交换消息并确认计划，随后达成约定。\r\n"
            if step == "episode_summary":
                assert body["response_format"] == {"type": "json_object"}
                text = json.dumps({"title": "测试事件", "summary": text}, ensure_ascii=False)
        return httpx.Response(200, json=reply(text))
    client = ModelClient(transport=httpx.MockTransport(handler), recording_directory=tmp_path)
    try:
        if failed_step:
            with pytest.raises(ArchiveExecutionError) as error:
                confirm_archive(database, client, archive_chat, ArchiveConfirm(**payload(previous[-1])))
            progress = error.value.progress
            result = retry_archive(database, client, archive_chat, progress.round.id, failed_step)
        else:
            result = confirm_archive(database, client, archive_chat, ArchiveConfirm(**payload(previous[-1])))
    finally:
        client.close()
    assert result.round.archive_step == "complete"
    assert result.round.summary == " 2026/10/20 回合摘要\r\n" and result.episode.summary == " 2026/10/19 用户与角色交换消息并确认计划，随后达成约定。\r\n"
    assert result.episode.title == "测试事件"
    assert result.state.content["世界"]["日期"] == "2026-10-20"
    assert len(calls) == 3 + bool(failed_step)
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(tmp_path.glob("*/metadata.json"))]
    assert [r["purpose"] for r in rows] == calls
    for row in rows:
        assert row["model"] == "deepseek-flash" and row["round_id"] == result.round.id
        assert row["api_type"] == API and row["response_complete"]
    if failed_step:
        retried = [r for r in rows if r["purpose"] == failed_step]
        assert [r["attempt"] for r in retried] == [1, 2]
        assert retried[0]["result"] == "http" and retried[1]["workflow_result"] == "success"
