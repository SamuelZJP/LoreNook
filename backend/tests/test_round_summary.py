from copy import deepcopy
import json

import httpx
import pytest
from sqlalchemy import update

from backend.llm.client import ModelClient
from backend.repository.archive import ArchiveRepository
from backend.repository.models import (
    Character, Chat, ChatModelBinding, Definition, ModelConfig, Round, StateSnapshot,
    UserIdentity, WritingPreset,
)
from backend.repository.queries import Repository
from backend.tests.test_catalog_api import run_api
from backend.tests.test_writing import database_contents
from backend.workflows.round_summary import run_round_summary

SUMMARY = " 2026-10-20 09:30，教室。角色与用户交换了重要消息。\r\n约定稍后见面。\n"
STATE = {"世界": {"日期": "2026-10-20", "时间": "09:30", "地点": "教室"}, "年龄": 17}


def text_response(text=SUMMARY):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def summary_round(database, chat):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        record = repo.create_round(chat[0], " 用户的输入\r\n", "<report_nya~>不应提供的报告</report_nya~><content> 正文\r\n </content><other>不应提供的附加内容</other>")
        state = repo.save_state(record.id, STATE)
        model = repo.add(ModelConfig(chat_id=chat[0], name="摘要模型", api_type="google_generate_content",
                                    base_url="https://provider.test/v1beta", api_key="summary-key", model="summary-model",
                                    default_parameters={"generationConfig": {"temperature": 0.7, "candidateCount": 4,
                                                                              "responseMimeType": "application/json"}}))
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="round_summary", model_config_id=model.id))
        # Definition and writing preset failures do not participate in built-in archiving.
        repo.add(Definition(character_id=chat[1], enabled=True, has_template=True, content="{{ missing }}"))
        preset = repo.add(WritingPreset(chat_id=chat[0], name="未完成写作预设", source="broken("))
        repo.get(Chat, chat[0]).writing_preset_id = preset.id
        return {"chat_id": chat[0], "character_id": chat[1], "round_id": record.id,
                "state_id": state.id, "model_id": model.id}


def assert_round_only_changed(before, after, round_id, **changes):
    expected = deepcopy(before)
    record = next(row for row in expected["rounds"] if row["id"] == round_id)
    record.update(changes)
    assert after == expected


def test_generation_uses_current_state_and_saves_only_summary_and_step(database, summary_round):
    ids, calls = summary_round, []
    before = database_contents(database)
    def handler(request):
        assert database.engine.pool.checkedout() == 0
        calls.append(request)
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "summary-key"
        assert request.url.path == "/v1beta/models/summary-model:generateContent"
        assert body["generationConfig"] == {"candidateCount": 1, "responseMimeType": "text/plain", "temperature": 0.7}
        text = body["contents"][0]["parts"][0]["text"]
        assert "日期: '2026-10-20'" in text and "时间: 09:30" in text and "地点: 教室" in text
        assert "日期: 2026-10-19" not in text and "年龄: 17" in text
        assert "用户的输入\r\n" in text and " 正文\r\n " in text
        assert "不应提供" not in text and "broken(" not in text and "{{ missing }}" not in text
        assert "角色" in text and "身份" in text
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"thought": True, "text": "不进入摘要的原生思考"},
            {"text": SUMMARY[:14]}, {"text": SUMMARY[14:]},
        ]}}]})
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}"
        assert (await client.get(root + "/summary")).status_code == 409
        result = await client.post(root + "/round-summary")
        assert result.status_code == 200, result.text
        assert result.json() == {"chat_id": ids["chat_id"], "round_id": ids["round_id"],
                                 "archive_step": "episode_decision", "summary": SUMMARY}
        assert (await client.get(root + "/summary")).json()["summary"] == SUMMARY
        assert (await client.post(root + "/round-summary")).status_code == 409
        # A saved summary alone does not complete archiving or permit manual editing.
        assert (await client.put(root + "/summary", json={"summary": "不能修改"})).status_code == 409
        assert (await client.post(f"/api/chats/{ids['chat_id']}/writing", json={"user_input": "下一回合"})).status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 1
    assert_round_only_changed(before, database_contents(database), ids["round_id"],
                               summary=SUMMARY, archive_step="episode_decision")


@pytest.mark.parametrize("bad", [
    {}, {"candidates": []}, {"candidates": [None]}, {"candidates": [{}, {}]},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "截断摘要"}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": None}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [1]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": 3}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"thought": True, "text": "只有思考"}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"functionCall": {"name": "unexpected"}}]}}]},
    text_response(" \r\n"),
])
def test_bad_response_is_not_saved_and_can_be_retried(database, summary_round, bad):
    ids, calls = summary_round, []
    before = database_contents(database)
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=bad if len(calls) == 1 else text_response())
    async def scenario(client):
        path = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/round-summary"
        failed = await client.post(path)
        assert failed.status_code == 422, failed.text
        after_failure = database_contents(database)
        failed_row = next(row for row in after_failure["rounds"] if row["id"] == ids["round_id"])
        assert failed_row["archive_step"] == "round_summary" and failed_row["summary"] is None
        assert failed_row["archive_error"]
        assert_round_only_changed(before, after_failure, ids["round_id"], archive_error=failed_row["archive_error"])
        retry = await client.post(path)
        assert retry.status_code == 200 and retry.json()["summary"] == SUMMARY
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2
    assert_round_only_changed(before, database_contents(database), ids["round_id"],
                               summary=SUMMARY, archive_step="episode_decision", archive_error=None)


@pytest.mark.parametrize("failure,status", [("http", 502), ("timeout", 504), ("network", 502), ("json", 502), ("body", 422)])
def test_call_or_body_error_preserves_state_and_saved_body(database, summary_round, failure, status):
    ids = summary_round
    if failure == "body":
        with database.transaction() as session:
            Repository(session).get(Round, ids["round_id"]).ai_output = "缺少 content"
    before, calls = database_contents(database), []
    def handler(request):
        calls.append(request)
        if failure == "http":
            return httpx.Response(429, json={"error": "summary-key"})
        if failure == "timeout":
            raise httpx.ReadTimeout("summary-key", request=request)
        if failure == "network":
            raise httpx.ConnectError("summary-key", request=request)
        return httpx.Response(200, content=b"bad-json")
    async def scenario(client):
        response = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/round-summary")
        assert response.status_code == status and "summary-key" not in response.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == (0 if failure == "body" else 1)
    after = database_contents(database)
    error = next(row["archive_error"] for row in after["rounds"] if row["id"] == ids["round_id"])
    assert error and "summary-key" not in error
    assert_round_only_changed(before, after, ids["round_id"], archive_error=error)


@pytest.mark.parametrize("case,status", [("missing_state", 409), ("missing_binding", 409),
    ("already_saved", 409), ("wrong_step", 409), ("unsupported", 422), ("missing_round", 404)])
def test_preconditions_do_not_call_model(database, summary_round, case, status):
    ids = summary_round
    with database.transaction() as session:
        repo = Repository(session)
        if case == "missing_state":
            repo.delete(repo.get(StateSnapshot, ids["state_id"]))  # initial state still exists
        elif case == "missing_binding":
            repo.delete(repo.model_binding(ids["chat_id"], "round_summary"))
        elif case == "already_saved":
            repo.get(Round, ids["round_id"]).summary = "已保存但未推进"
        elif case == "wrong_step":
            repo.get(Round, ids["round_id"]).archive_step = "state_update"
        elif case == "unsupported":
            repo.get(ModelConfig, ids["model_id"]).api_type = "other"
    calls = []
    async def scenario(client):
        rid = "missing" if case == "missing_round" else ids["round_id"]
        response = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{rid}/round-summary")
        assert response.status_code == status, response.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == []


def test_scope_isolation_for_generation_reading_and_editing(database, summary_round):
    ids = summary_round
    with database.transaction() as session:
        repo = Repository(session)
        other = repo.add(Chat(title="其他聊天")).id
        repo.add(Character(chat_id=other, name="其他角色"))
        repo.add(UserIdentity(chat_id=other, name="其他用户"))
    async def scenario(client):
        foreign = f"/api/chats/{other}/rounds/{ids['round_id']}"
        assert (await client.post(foreign + "/round-summary")).status_code == 404
        assert (await client.get(foreign + "/summary")).status_code == 404
        assert (await client.put(foreign + "/summary", json={"summary": "越界"})).status_code == 404
        assert (await client.post(f"/api/chats/missing/rounds/{ids['round_id']}/round-summary")).status_code == 404
    run_api(database, scenario)


@pytest.mark.parametrize("change", ["state", "state_type", "body", "connection"])
def test_stale_input_cannot_save_summary(database, summary_round, change):
    ids = summary_round
    if change == "state_type":
        with database.transaction() as session:
            Repository(session).get(StateSnapshot, ids["state_id"]).content = {"值": 1}
    def handler(request):
        with database.transaction() as session:
            repo = Repository(session)
            if change == "state":
                repo.get(StateSnapshot, ids["state_id"]).content = {"新值": True}
            elif change == "state_type":
                session.execute(update(StateSnapshot).where(StateSnapshot.id == ids["state_id"]).values(content={"值": True}))
            elif change == "body":
                repo.get(Round, ids["round_id"]).user_input = "已编辑输入"
            else:
                repo.get(ModelConfig, ids["model_id"]).api_key = "changed-key"
        return httpx.Response(200, json=text_response())
    async def scenario(client):
        response = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/round-summary")
        assert response.status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        record = Repository(session).get(Round, ids["round_id"])
        assert record.summary is None and record.archive_step == "round_summary" and record.archive_error is None


def test_stale_failure_does_not_overwrite_newly_saved_result(database, summary_round):
    ids = summary_round
    def handler(request):
        with database.transaction() as session:
            ArchiveRepository(session).save_summary(ids["round_id"], "另一个请求已保存的摘要")
        return httpx.Response(429, json={})
    async def scenario(client):
        response = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/round-summary")
        assert response.status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        record = Repository(session).get(Round, ids["round_id"])
        assert record.summary == "另一个请求已保存的摘要" and record.archive_error is None


def test_summary_save_rollback_is_atomic(database, summary_round, monkeypatch):
    ids, before = summary_round, database_contents(database)
    original = ArchiveRepository.save_summary
    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("提交前失败")
    monkeypatch.setattr(ArchiveRepository, "save_summary", fail)
    client = ModelClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=text_response())))
    try:
        with pytest.raises(RuntimeError):
            run_round_summary(database, client, ids["chat_id"], ids["round_id"])
    finally:
        client.close()
    assert database_contents(database) == before


def test_manual_summary_edit_keeps_original_text_and_does_not_recompute(database, summary_round):
    ids = summary_round
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_summary(ids["round_id"], "原摘要")
        repo.save_decision(ids["round_id"])
    before = database_contents(database)
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}"
        response = await client.put(root + "/summary", json={"summary": SUMMARY})
        assert response.status_code == 200 and response.json()["summary"] == SUMMARY
        assert (await client.get(root + "/summary")).json()["summary"] == SUMMARY
        for invalid in ({"summary": " "}, {"summary": None}, {"summary": 3}, {"summary": "x", "round_id": "other"}):
            assert (await client.put(root + "/summary", json=invalid)).status_code == 422
    run_api(database, scenario)
    assert_round_only_changed(before, database_contents(database), ids["round_id"], summary=SUMMARY)
    with database.transaction() as session:
        ArchiveRepository(session).create_round(ids["chat_id"], "下一回合", "<content>正文</content>")
    async def after_next(client):
        path = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/summary"
        assert (await client.get(path)).status_code == 200
        assert (await client.put(path, json={"summary": "已不是最新回合"})).status_code == 409
    run_api(database, after_next)


@pytest.mark.parametrize("window", [3, 0])
def test_recent_summaries_window_includes_episode_covered_rounds(database, summary_round, window):
    ids = summary_round
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_summary(ids["round_id"], "旧摘要1")
        repo.save_decision(ids["round_id"])
        round_ids = [ids["round_id"]]
        for number in range(2, 6):
            record = repo.create_round(ids["chat_id"], f"旧输入{number}", "<content>旧正文</content>")
            round_ids.append(record.id)
            repo.save_state(record.id, STATE)
            repo.save_summary(record.id, f"旧摘要{number}")
            if number == 5:
                repo.save_decision(record.id, start_round_id=round_ids[0], end_round_id=round_ids[3])
                repo.save_episode(record.id, "历史情节不进入此请求")
            else:
                repo.save_decision(record.id)
        current = repo.create_round(ids["chat_id"], "本回合输入", "<content>本回合正文</content>")
        repo.save_state(current.id, STATE | {"年龄": 22})
        current_id = current.id
    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "旧摘要1" not in prompt and "旧摘要2" not in prompt
        if window:
            assert prompt.index("第3回合：旧摘要3") < prompt.index("第4回合：旧摘要4") < prompt.index("第5回合：旧摘要5")
        else:
            assert "旧摘要" not in prompt
        assert "历史情节不进入此请求" not in prompt and "旧正文" not in prompt
        assert "本回合正文" in prompt and "年龄: 22" in prompt
        return httpx.Response(200, json=text_response())
    client = ModelClient(transport=httpx.MockTransport(handler))
    try:
        result = run_round_summary(database, client, ids["chat_id"], current_id, recent_summaries=window)
        assert result.summary == SUMMARY and result.archive_step == "episode_decision"
    finally:
        client.close()


def test_state_update_then_summary_uses_newly_generated_state(database, summary_round):
    ids = summary_round
    with database.transaction() as session:
        repo = Repository(session)
        repo.delete(repo.get(StateSnapshot, ids["state_id"]))
        repo.get(Round, ids["round_id"]).archive_step = "state_update"
        repo.add(ChatModelBinding(chat_id=ids["chat_id"], purpose="state_update", model_config_id=ids["model_id"]))
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        prompt = body["contents"][0]["parts"][0]["text"]
        if len(calls) == 1:
            assert "年龄: 16" in prompt and body["generationConfig"]["responseMimeType"] == "text/plain"
            return httpx.Response(200, json=text_response('<UpdateVariable><Analysis>本轮结算。</Analysis><JSONPatch>' + json.dumps([
                {"op": "replace", "path": "/年龄", "value": 18},
                {"op": "replace", "path": "/世界/日期", "value": "2026-10-20"},
                {"op": "add", "path": "/世界/时间", "value": "09:30"},
                {"op": "add", "path": "/世界/地点", "value": "教室"},
            ], ensure_ascii=False) + '</JSONPatch></UpdateVariable>'))
        assert "年龄: 18" in prompt and "年龄: 16" not in prompt
        assert "时间: 09:30" in prompt and "地点: 教室" in prompt
        assert body["generationConfig"]["responseMimeType"] == "text/plain"
        return httpx.Response(200, json=text_response())
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}"
        state = await client.post(root + "/state-update")
        assert state.status_code == 200 and state.json()["archive_step"] == "round_summary"
        summary = await client.post(root + "/round-summary")
        assert summary.status_code == 200 and summary.json()["archive_step"] == "episode_decision"
        assert (await client.post(root + "/state-update")).status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2
