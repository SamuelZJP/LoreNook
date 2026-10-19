from copy import deepcopy
import json

import httpx
import pytest
from sqlalchemy import update

from backend.llm.client import ModelClient
from backend.repository.archive import ArchiveRepository
from backend.repository.models import (
    Character, Chat, ChatModelBinding, Definition, Episode, ModelConfig, Round, StateSnapshot, WritingPreset,
)
from backend.repository.queries import Repository
from backend.tests.test_catalog_api import run_api
from backend.tests.test_round_summary import assert_round_only_changed
from backend.tests.test_writing import database_contents
from backend.workflows.episode_summary import run_episode_summary
from backend.shared.errors import ConflictError

TEXT = " 2026-10-19在教室发生了一系列事件，角色逐步确认了计划。\r\n最终达成约定。\n"
TITLE = "课堂约定"


def episode_json(text=TEXT):
    return json.dumps({"title": TITLE, "summary": text}, ensure_ascii=False)


def text_response(text=TEXT):
    if text == TEXT:
        text = episode_json(text)
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def pending_episode(database, chat):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        ids = []
        for number in range(1, 7):
            record = repo.create_round(chat[0], f"完整用户输入{number}",
                                      f"<report_nya~>不提供的报告{number}</report_nya~><content>完整 AI 正文{number}</content>")
            ids.append(record.id)
            repo.save_state(record.id, {"世界": {"日期": "2026-10-20" if number == 6 else "2026-10-19", "时间": f"{number}:00"}, "编号": number})
            repo.save_summary(record.id, f"回合摘要{number}\r\n")
            if number < 6:
                repo.save_decision(record.id)
        repo.save_decision(ids[-1], start_round_id=ids[0], end_round_id=ids[4])
        model = repo.add(ModelConfig(chat_id=chat[0], name="情节模型", api_type="google_generate_content",
                                    base_url="https://provider.test/v1beta", api_key="episode-key", model="episode-model",
                                    default_parameters={"generationConfig": {"temperature": 0.6, "candidateCount": 4,
                                                                              "responseMimeType": "application/json"}}))
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="episode_summary", model_config_id=model.id))
        repo.get(Character, chat[1]).state_schema = "broken schema source"
        repo.add(Definition(character_id=chat[1], has_template=True, content="{{ missing }}"))
        preset = repo.add(WritingPreset(chat_id=chat[0], name="未完成预设", source="broken("))
        repo.get(Chat, chat[0]).writing_preset_id = preset.id
        return {"chat_id": chat[0], "character_id": chat[1], "round_id": ids[-1], "ids": ids, "model_id": model.id}


def assert_success_changes(before, after, ids, summary=TEXT):
    for name in before.keys() - {"rounds", "episodes"}:
        assert before[name] == after[name]
    expected_rounds = deepcopy(before["rounds"])
    creator = next(row for row in expected_rounds if row["id"] == ids["round_id"])
    creator.update(archive_step="complete", archive_error=None)
    assert after["rounds"] == expected_rounds
    old = {row["id"]: row for row in before["episodes"]}
    assert all(next(row for row in after["episodes"] if row["id"] == eid) == row for eid, row in old.items())
    added = [row for row in after["episodes"] if row["id"] not in old]
    assert len(added) == 1
    assert added[0]["summary"] == summary and added[0]["created_by_round_id"] == ids["round_id"]
    assert added[0]["start_round_id"] == creator["episode_start_round_id"]
    assert added[0]["end_round_id"] == creator["episode_end_round_id"]


def test_episode_summary_uses_selected_dialogue_summaries_and_states(database, pending_episode):
    ids, calls = pending_episode, []
    before = database_contents(database)
    def handler(request):
        calls.append(request)
        assert database.engine.pool.checkedout() == 0
        assert request.headers["x-goog-api-key"] == "episode-key"
        assert request.url.path == "/v1beta/models/episode-model:generateContent"
        body = json.loads(request.content)
        assert body["generationConfig"] == {"candidateCount": 1, "responseMimeType": "application/json", "temperature": 0.6}
        prompt = body["contents"][0]["parts"][0]["text"]
        assert "第 1—5 回合" in prompt and "角色" in prompt and "身份" in prompt
        assert [prompt.index(f"回合摘要{number}\r\n") for number in range(1, 6)] == sorted(prompt.index(f"回合摘要{number}\r\n") for number in range(1, 6))
        assert "回合摘要6" not in prompt and "2026-10-20" not in prompt and "编号: 6" not in prompt
        assert "完整用户输入1" in prompt and "完整 AI 正文5" in prompt
        assert "完整用户输入6" not in prompt and "完整 AI 正文6" not in prompt
        assert "不提供的报告" not in prompt and "broken" not in prompt
        assert "2026-10-19" in prompt and "编号: 5" in prompt
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"thought": True, "text": "不保存的原生思考"}, {"text": episode_json()[:10]}, {"text": episode_json()[10:]},
        ]}}]})
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}"
        path = root + f"/rounds/{ids['round_id']}/episode-summary"
        assert (await client.get(root + "/episodes")).json() == []
        result = await client.post(path)
        assert result.status_code == 200, result.text
        payload = result.json()
        assert payload["archive_step"] == "complete" and payload["episode"]["summary"] == TEXT
        episode = payload["episode"]
        assert episode["title"] == TITLE
        assert episode["start_round_id"] == ids["ids"][0] and episode["end_round_id"] == ids["ids"][4]
        assert episode["created_by_round_id"] == ids["round_id"]
        assert (await client.get(root + f"/episodes/{episode['id']}")).json() == episode
        assert (await client.post(path)).status_code == 409
        # The saved episode need not enter writing memory immediately (X=5, Y=6).
        memory = (await client.get(root + "/memory")).json()
        assert not any(item["kind"] == "episode" for item in memory["items"])
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 1
    assert_success_changes(before, database_contents(database), ids)
    with database.read() as session:
        assert [r.id for r in Repository(session).unrepresented_rounds(ids["chat_id"])] == [ids["round_id"]]


@pytest.mark.parametrize("bad", [
    {}, {"candidates": []}, {"candidates": [{}, {}]},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "未完成"}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"thought": True, "text": "只有思考"}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"functionCall": {"name": "工具"}}]}}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [3]}}]}, text_response(" \r\n"),
])
def test_invalid_text_keeps_range_and_boundary_then_retry_succeeds(database, pending_episode, bad):
    ids, calls = pending_episode, []
    before = database_contents(database)
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=bad if len(calls) == 1 else text_response())
    async def scenario(client):
        path = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary"
        failed = await client.post(path)
        assert failed.status_code == 422, failed.text
        after = database_contents(database)
        error = next(row["archive_error"] for row in after["rounds"] if row["id"] == ids["round_id"])
        assert error
        assert_round_only_changed(before, after, ids["round_id"], archive_error=error)
        with database.read() as session:
            assert [r.id for r in Repository(session).unrepresented_rounds(ids["chat_id"])] == ids["ids"]
        retried = await client.post(path)
        assert retried.status_code == 200 and retried.json()["episode"]["summary"] == TEXT
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2
    assert_success_changes(before, database_contents(database), ids)


@pytest.mark.parametrize("failure,status", [("http", 502), ("timeout", 504), ("network", 502), ("json", 502)])
def test_call_failure_does_not_move_boundary(database, pending_episode, failure, status):
    ids = pending_episode
    before = database_contents(database)
    def handler(request):
        if failure == "http":
            return httpx.Response(429, json={"error": "episode-key"})
        if failure == "timeout":
            raise httpx.ReadTimeout("episode-key", request=request)
        if failure == "network":
            raise httpx.ConnectError("episode-key", request=request)
        return httpx.Response(200, content=b"not-json")
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary")
        assert result.status_code == status and "episode-key" not in result.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    after = database_contents(database)
    error = next(row["archive_error"] for row in after["rounds"] if row["id"] == ids["round_id"])
    assert error and "episode-key" not in error
    assert_round_only_changed(before, after, ids["round_id"], archive_error=error)


@pytest.mark.parametrize("case,status", [("missing_binding", 409), ("missing_state", 409),
    ("bad_start", 409), ("bad_end", 409), ("wrong_step", 409), ("already_saved", 409), ("unsupported", 422)])
def test_invalid_range_or_configuration_stops_before_network(database, pending_episode, case, status):
    ids = pending_episode
    with database.transaction() as session:
        repo = Repository(session)
        if case == "missing_binding":
            repo.delete(repo.model_binding(ids["chat_id"], "episode_summary"))
        elif case == "missing_state":
            repo.delete(repo.state_for_round(ids["chat_id"], ids["ids"][2]))
        elif case == "bad_start":
            repo.get(Round, ids["round_id"]).episode_start_round_id = ids["ids"][1]
        elif case == "bad_end":
            repo.get(Round, ids["round_id"]).episode_end_round_id = ids["round_id"]
        elif case == "wrong_step":
            record = repo.get(Round, ids["round_id"])
            record.archive_step, record.episode_required = "complete", False
            record.episode_start_round_id = record.episode_end_round_id = None
        elif case == "already_saved":
            repo.add(Episode(chat_id=ids["chat_id"], start_round_id=ids["ids"][0], end_round_id=ids["ids"][4],
                             created_by_round_id=ids["round_id"], summary="异常的部分结果"))
        else:
            repo.get(ModelConfig, ids["model_id"]).api_type = "other"
    calls = []
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary")
        assert result.status_code == status, result.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == []


def test_retry_keeps_saved_partial_range_without_redeciding(database, pending_episode, monkeypatch):
    ids = pending_episode
    with database.transaction() as session:
        Repository(session).get(Round, ids["round_id"]).episode_end_round_id = ids["ids"][2]
    from backend.modules.episode_decision import dispatcher
    monkeypatch.setattr(dispatcher, "decide_episode", lambda *args, **kwargs: pytest.fail("不应重新判定"))
    calls = []
    def handler(request):
        calls.append(request)
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "第 1—3 回合" in prompt and "回合摘要4" not in prompt and "回合摘要5" not in prompt
        return httpx.Response(429, json={}) if len(calls) == 1 else httpx.Response(200, json=text_response())
    async def scenario(client):
        path = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary"
        assert (await client.post(path)).status_code == 502
        with database.transaction() as session:
            # Even a change to the deciding round's date does not recalculate its saved range.
            Repository(session).state_for_round(ids["chat_id"], ids["round_id"]).content = {"世界": {"日期": "2026-10-19"}}
        result = await client.post(path)
        assert result.status_code == 200 and result.json()["episode"]["end_round_id"] == ids["ids"][2]
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["state", "state_type", "summary", "range", "key", "user_input", "ai_output", "first_message"])
def test_changed_input_cannot_save_stale_episode(database, pending_episode, change):
    ids = pending_episode
    if change == "state_type":
        with database.transaction() as session:
            Repository(session).state_for_round(ids["chat_id"], ids["ids"][0]).content = {"值": 1}
    def handler(request):
        with database.transaction() as session:
            repo = Repository(session)
            state = repo.state_for_round(ids["chat_id"], ids["ids"][0])
            if change == "state":
                state.content = {"改变": True}
            elif change == "state_type":
                session.execute(update(StateSnapshot).where(StateSnapshot.id == state.id).values(content={"值": True}))
            elif change == "summary":
                repo.get(Round, ids["ids"][0]).summary = "修改过的回合摘要"
            elif change == "range":
                repo.get(Round, ids["round_id"]).episode_end_round_id = ids["ids"][2]
            elif change in {"user_input", "ai_output"}:
                setattr(repo.get(Round, ids["ids"][0]), change, "修改后的输入" if change == "user_input" else "<content>修改后正文</content>")
            elif change == "first_message":
                repo.get(Character, ids["character_id"]).first_message = "修改后的开场"
            else:
                repo.get(ModelConfig, ids["model_id"]).api_key = "changed-key"
        return httpx.Response(200, json=text_response())
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary")
        assert result.status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        repo = Repository(session)
        assert repo.episodes(ids["chat_id"]) == []
        assert repo.get(Round, ids["round_id"]).archive_step == "episode_summary"


@pytest.mark.parametrize("failed_response", [False, True])
def test_competing_saved_episode_is_not_overwritten(database, pending_episode, failed_response):
    ids = pending_episode
    def handler(request):
        with database.transaction() as session:
            ArchiveRepository(session).save_episode(ids["round_id"], "另一个请求的成功结果")
        return httpx.Response(429, json={}) if failed_response else httpx.Response(200, json=text_response())
    async def scenario(client):
        result = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary")
        assert result.status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        repo = Repository(session)
        assert len(repo.episodes(ids["chat_id"])) == 1
        assert repo.episodes(ids["chat_id"])[0].summary == "另一个请求的成功结果"
        assert repo.get(Round, ids["round_id"]).archive_error is None


def test_episode_save_rollback_preserves_boundary(database, pending_episode, monkeypatch):
    ids, before = pending_episode, database_contents(database)
    original = ArchiveRepository.save_episode
    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("保存情节后提交前失败")
    monkeypatch.setattr(ArchiveRepository, "save_episode", fail)
    client = ModelClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=text_response())))
    try:
        with pytest.raises(RuntimeError):
            run_episode_summary(database, client, ids["chat_id"], ids["round_id"])
    finally:
        client.close()
    assert database_contents(database) == before


def test_episode_read_edit_scope_and_latest_producer_rule(database, pending_episode):
    ids = pending_episode
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        episode_id = repo.save_episode(ids["round_id"], "原情节").id
        other = repo.add(Chat(title="另一个聊天")).id
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}"
        path = root + f"/episodes/{episode_id}"
        assert (await client.get(path)).json()["summary"] == "原情节"
        edited = await client.put(path, json={"summary": TEXT})
        assert edited.status_code == 200 and edited.json()["summary"] == TEXT
        for invalid in ({"summary": " "}, {"summary": None}, {"summary": 3}, {"summary": "x", "start_round_id": "override"}):
            assert (await client.put(path, json=invalid)).status_code == 422
        assert (await client.get(f"/api/chats/{other}/episodes/{episode_id}")).status_code == 404
        assert (await client.put(f"/api/chats/{other}/episodes/{episode_id}", json={"summary": "越界"})).status_code == 404
        assert (await client.post(f"/api/chats/{other}/rounds/{ids['round_id']}/episode-summary")).status_code == 404
        assert (await client.get("/api/chats/missing/episodes")).status_code == 404
        with database.transaction() as session:
            ArchiveRepository(session).create_round(ids["chat_id"], "下一回合", "输出")
        assert (await client.put(path, json={"summary": "不再可编辑"})).status_code == 409
        assert (await client.get(path)).json()["summary"] == TEXT
    run_api(database, scenario)


def test_next_episode_excludes_covered_rounds_and_old_episode(database, pending_episode):
    ids = pending_episode
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        first_id = repo.save_episode(ids["round_id"], "不可作为额外上下文的旧情节").id
        later = []
        for number in range(7, 12):
            record = repo.create_round(ids["chat_id"], "完整输入", "<content>完整输出</content>")
            later.append(record.id)
            repo.save_state(record.id, {"世界": {"日期": "2026-10-21" if number == 11 else "2026-10-20"}})
            repo.save_summary(record.id, f"回合摘要{number}")
            if number < 11:
                repo.save_decision(record.id)
        repo.save_decision(later[-1], start_round_id=ids["round_id"], end_round_id=later[-2])
    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "第 6—10 回合" in prompt
        assert all(f"回合摘要{number}" in prompt for number in range(6, 11))
        assert "回合摘要1\r\n" not in prompt and "旧情节" not in prompt and "2026-10-19" not in prompt
        assert "回合5摘要" in prompt and "完整 AI 正文5" in prompt  # preceding covered bridge only
        assert "回合摘要11" not in prompt and "2026-10-21" not in prompt
        return httpx.Response(200, json=text_response(episode_json("第二个情节")))
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}"
        result = await client.post(root + f"/rounds/{later[-1]}/episode-summary")
        assert result.status_code == 200, result.text
        second = result.json()["episode"]
        assert second["start_round_id"] == ids["round_id"] and second["end_round_id"] == later[-2]
        assert [row["id"] for row in (await client.get(root + "/episodes")).json()] == [first_id, second["id"]]
        assert (await client.put(root + f"/episodes/{first_id}", json={"summary": "旧情节修改"})).status_code == 409
        assert (await client.put(root + f"/episodes/{second['id']}", json={"summary": "新情节修改"})).status_code == 200
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    with database.read() as session:
        assert [r.id for r in Repository(session).unrepresented_rounds(ids["chat_id"])] == [later[-1]]


def test_round_summary_decision_episode_chain(database, pending_episode):
    ids, calls = pending_episode, []
    with database.transaction() as session:
        repo = Repository(session)
        record = repo.get(Round, ids["round_id"])
        record.summary, record.archive_step = None, "round_summary"
        record.episode_required = record.episode_start_round_id = record.episode_end_round_id = None
        record.ai_output = "<content>第六回合正文</content>"
        repo.add(ChatModelBinding(chat_id=ids["chat_id"], purpose="round_summary", model_config_id=ids["model_id"]))
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=text_response("第六回合摘要" if len(calls) == 1 else TEXT))
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}"
        summary = await client.post(root + "/round-summary")
        assert summary.status_code == 200, summary.text
        decision = await client.post(root + "/episode-decision")
        assert decision.status_code == 200 and decision.json()["archive_step"] == "episode_summary"
        with database.transaction() as session:
            with pytest.raises(ConflictError):
                ArchiveRepository(session).create_round(ids["chat_id"], "下一回合", "输出")
        result = await client.post(root + "/episode-summary")
        assert result.status_code == 200 and result.json()["archive_step"] == "complete"
        with database.transaction() as session:
            assert ArchiveRepository(session).create_round(ids["chat_id"], "下一回合", "输出").round_no == 7
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2


def test_save_episode_revalidates_frozen_range(database, pending_episode):
    ids = pending_episode
    with database.transaction() as session:
        Repository(session).get(Round, ids["round_id"]).episode_start_round_id = ids["ids"][1]
    before = database_contents(database)
    with pytest.raises(ConflictError):
        with database.transaction() as session:
            ArchiveRepository(session).save_episode(ids["round_id"], "不能保存")
    assert database_contents(database) == before
