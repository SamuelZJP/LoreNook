from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest
from sqlalchemy import event

from backend.modules.episode_decision import dispatcher
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Chat, ChatModelBinding, ModelConfig, Round, StateSnapshot
from backend.repository.queries import Repository
from backend.schemas.episode_decision import EpisodeCandidate, EpisodeDecisionContext
from backend.shared.errors import ConflictError, EpisodeDecisionError
from backend.tests.test_catalog_api import run_api
from backend.tests.test_writing import database_contents
from backend.workflows.episode_decision import run_episode_decision


def context(count, *, start=1, previous="2026-10-19", current="2026-10-20"):
    candidates = [EpisodeCandidate(id=f"r{i}", round_no=i) for i in range(start, start + count)]
    dates = {candidates[-1].id: current} if candidates else {}
    if len(candidates) > 1:
        dates[candidates[-2].id] = previous
    return EpisodeDecisionContext(current_round_id=candidates[-1].id if candidates else "missing",
                                   candidates=candidates, dates=dates)


@pytest.mark.parametrize("count,previous,current,required", [
    (1, None, None, False), (5, None, None, False), (5, "2026-10-19", "2026-10-20", False),
    (6, "2026-10-19", "2026-10-19", False), (6, "2026-10-19", "2026-10-20", True),
    (9, "2026-10-19", "2026-10-20", True), (9, "2026-10-19", "2026-10-19", False),
    (6, "2026-10-20", "2026-10-19", True),
])
def test_threshold_then_parsed_date_comparison(count, previous, current, required):
    source = context(count, start=13, previous=previous, current=current)
    before = source.model_dump()
    result = dispatcher.decide_episode(source)
    assert result.episode_required is required
    if required:
        assert (result.start_round_no, result.end_round_no) == (13, 13 + count - 2)
        assert (result.start_round_id, result.end_round_id) == ("r13", f"r{13 + count - 2}")
    else:
        assert result.start_round_id is None and result.end_round_id is None
    assert source.model_dump() == before


@pytest.mark.parametrize("date", [None, "", " \n", 3, True, {}, [], ["日期"], "第一天", "2026-10-19 星期一", "2026-10-19 ", "2026-02-30", "2026-1-01"])
def test_missing_or_wrong_date_type_is_not_a_negative_fallback(date):
    with pytest.raises(EpisodeDecisionError):
        dispatcher.decide_episode(context(6, current=date))
    with pytest.raises(EpisodeDecisionError):
        dispatcher.decide_episode(context(6, previous=date))


def test_dispatcher_sorts_and_supports_other_cutoff_methods(monkeypatch):
    source = context(8, start=13)
    source.candidates.reverse()
    before = source.model_dump()
    monkeypatch.setitem(dispatcher.METHODS, "partial", lambda data: data.candidates[4].id)
    monkeypatch.setattr(dispatcher, "DEFAULT_METHOD", "partial")
    result = dispatcher.decide_episode(source)
    assert (result.start_round_no, result.end_round_no) == (13, 17)
    assert source.model_dump() == before
    assert dispatcher.decide_episode(source, method="day_boundary").end_round_no == 19


def test_method_input_is_detached_from_caller_context(monkeypatch):
    source = context(6)
    before = source.model_dump()
    def method(data):
        end_id = data.candidates[2].id
        data.candidates[0].id = "modified"
        data.dates[data.current_round_id] = "modified"
        return end_id
    monkeypatch.setitem(dispatcher.METHODS, "custom", method)
    result = dispatcher.decide_episode(source, method="custom")
    assert source.model_dump() == before
    assert result.start_round_id == "r1" and result.end_round_id == "r3"


@pytest.mark.parametrize("cutoff", ["missing", "r6", False, 3])
def test_dispatcher_rejects_ineligible_method_cutoff(monkeypatch, cutoff):
    monkeypatch.setitem(dispatcher.METHODS, "invalid", lambda data: cutoff)
    with pytest.raises(EpisodeDecisionError):
        dispatcher.decide_episode(context(6), method="invalid")


def test_unknown_method_has_no_fallback():
    with pytest.raises(EpisodeDecisionError):
        dispatcher.decide_episode(context(6), method="unknown")


@pytest.mark.parametrize("case", ["empty", "duplicate", "gap", "current_missing"])
def test_invalid_candidate_range_is_rejected(case):
    source = context(6)
    if case == "empty":
        source.candidates = []
    elif case == "duplicate":
        source.candidates.insert(1, source.candidates[0])
    elif case == "gap":
        source.candidates.pop(1)
    else:
        source.current_round_id = "missing"
    with pytest.raises(ConflictError):
        dispatcher.decide_episode(source)


def seed_rounds(database, chat_id, count, *, last_date="2026-10-20", previous_date="2026-10-19", dates=True):
    ids = []
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        for number in range(1, count + 1):
            record = repo.create_round(chat_id, "不参与判定的用户正文", "不参与判定的无标签 AI 输出")
            ids.append(record.id)
            date = last_date if number == count else previous_date
            state = {"世界": {"日期": date}, "其他": "不参与判定"} if dates else {}
            repo.save_state(record.id, state)
            repo.save_summary(record.id, "不参与判定的摘要")
            if number < count:
                repo.save_decision(record.id)
    return ids


@pytest.mark.parametrize("count,same_day,required", [(1, False, False), (5, False, False),
                                                     (6, True, False), (6, False, True)])
def test_http_decision_saves_exact_result_without_model(database, chat, count, same_day, required):
    ids = seed_rounds(database, chat[0], count, last_date="2026-10-19" if same_day else "2026-10-20", dates=count >= 6)
    before = database_contents(database)
    def no_model(request):
        pytest.fail("情节判定不应调用模型")
    async def scenario(client):
        path = f"/api/chats/{chat[0]}/rounds/{ids[-1]}/episode-decision"
        response = await client.post(path)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["episode_required"] is required
        assert result["archive_step"] == ("episode_summary" if required else "complete")
        assert result["start_round_id"] == (ids[0] if required else None)
        assert result["end_round_id"] == (ids[-2] if required else None)
        assert result["start_round_no"] == (1 if required else None)
        assert result["end_round_no"] == (count - 1 if required else None)
        assert (await client.post(path)).status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(no_model))
    expected = deepcopy(before)
    record = next(row for row in expected["rounds"] if row["id"] == ids[-1])
    record.update(episode_required=required, archive_step="episode_summary" if required else "complete",
                  episode_start_round_id=ids[0] if required else None,
                  episode_end_round_id=ids[-2] if required else None)
    assert database_contents(database) == expected
    with database.read() as session:
        repo = Repository(session)
        assert repo.episodes(chat[0]) == []
        assert [r.id for r in repo.unrepresented_rounds(chat[0])] == ids  # decision alone doesn't move coverage


@pytest.mark.parametrize("date", [None, "", 3, True, {}, []])
def test_projected_invalid_date_fails_and_keeps_step(database, chat, date):
    ids = seed_rounds(database, chat[0], 6, last_date=date)
    async def scenario(client):
        result = await client.post(f"/api/chats/{chat[0]}/rounds/{ids[-1]}/episode-decision")
        assert result.status_code == 422, result.text
    run_api(database, scenario)
    with database.read() as session:
        record = Repository(session).get(Round, ids[-1])
        assert record.archive_step == "episode_decision" and record.archive_error
        assert record.episode_required is None


def test_retry_after_fixing_missing_state_clears_error(database, chat):
    ids = seed_rounds(database, chat[0], 6)
    with database.transaction() as session:
        repo = Repository(session)
        state = repo.state_for_round(chat[0], ids[-2])
        state_id, state_content = state.id, state.content
        repo.delete(state)
    async def scenario(client):
        path = f"/api/chats/{chat[0]}/rounds/{ids[-1]}/episode-decision"
        assert (await client.post(path)).status_code == 422
        with database.transaction() as session:
            Repository(session).add(StateSnapshot(id=state_id, chat_id=chat[0], character_id=chat[1],
                                                   round_id=ids[-2], content=state_content))
        result = await client.post(path)
        assert result.status_code == 200 and result.json()["episode_required"] is True
    run_api(database, scenario)
    with database.read() as session:
        assert Repository(session).get(Round, ids[-1]).archive_error is None


def test_episode_covered_rounds_are_not_candidates_or_date_context(database, chat):
    ids = seed_rounds(database, chat[0], 6)
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_decision(ids[-1], start_round_id=ids[0], end_round_id=ids[-2])
        repo.save_episode(ids[-1], "覆盖1到5的情节")
        current = repo.create_round(chat[0], "用户", "输出")
        repo.save_state(current.id, {"世界": {"日期": "2026-10-21"}})
        repo.save_summary(current.id, "摘要")
        current_id = current.id
        # A covered round has an invalid date; it cannot leak into this method's state inputs.
        repo.state_for_round(chat[0], ids[-2]).content = {}
    reads = []
    original_dates = Repository.round_dates
    def capture(self, chat_id, round_ids):
        reads.extend(round_ids)
        return original_dates(self, chat_id, round_ids)
    from unittest.mock import patch
    with patch.object(Repository, "round_dates", capture):
        result = run_episode_decision(database, chat[0], current_id)
    assert result.episode_required is False and reads == [ids[-1], current_id]
    assert not set(ids[:-1]) & set(reads)


def test_next_range_begins_at_earliest_uncovered_round(database, chat):
    ids = seed_rounds(database, chat[0], 6)
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_decision(ids[-1], start_round_id=ids[0], end_round_id=ids[-2])
        repo.save_episode(ids[-1], "旧情节")
        for number in range(7, 12):
            record = repo.create_round(chat[0], "输入", "输出")
            ids.append(record.id)
            repo.save_state(record.id, {"世界": {"日期": "2026-10-21" if number == 11 else "2026-10-20"}})
            repo.save_summary(record.id, "摘要")
            if number < 11:
                repo.save_decision(record.id)
    result = run_episode_decision(database, chat[0], ids[-1])
    assert result.episode_required is True
    assert (result.start_round_no, result.end_round_no) == (6, 10)
    assert (result.start_round_id, result.end_round_id) == (ids[5], ids[9])


def test_scope_old_round_and_wrong_step_do_not_change_data(database, chat):
    ids = seed_rounds(database, chat[0], 2)
    with database.transaction() as session:
        repo = Repository(session)
        other = repo.add(Chat(title="其他聊天")).id
        repo.get(Round, ids[-1]).archive_step = "round_summary"
    before = database_contents(database)
    async def scenario(client):
        for chat_id, round_id, status in [("missing", ids[-1], 404), (other, ids[-1], 404),
                                          (chat[0], "missing", 404), (chat[0], ids[0], 409), (chat[0], ids[-1], 409)]:
            result = await client.post(f"/api/chats/{chat_id}/rounds/{round_id}/episode-decision")
            assert result.status_code == status, result.text
    run_api(database, scenario)
    assert database_contents(database) == before


def test_decision_save_and_progress_roll_back_together(database, chat, monkeypatch):
    ids = seed_rounds(database, chat[0], 6)
    before = database_contents(database)
    original = ArchiveRepository.save_decision
    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("提交前中断")
    monkeypatch.setattr(ArchiveRepository, "save_decision", fail)
    with pytest.raises(RuntimeError):
        run_episode_decision(database, chat[0], ids[-1])
    assert database_contents(database) == before


def test_concurrent_decisions_only_one_succeeds(database, chat):
    ids = seed_rounds(database, chat[0], 6)
    barrier = Barrier(2)
    def call():
        barrier.wait(timeout=5)
        try:
            return run_episode_decision(database, chat[0], ids[-1]).archive_step
        except ConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: call(), range(2)))
    assert sorted(results) == ["conflict", "episode_summary"]


def test_candidate_projection_does_not_load_story_text(database, chat):
    ids = seed_rounds(database, chat[0], 6)
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        with database.read() as session:
            repo = Repository(session)
            assert [r.id for r in repo.unrepresented_round_headers(chat[0])] == ids
            assert repo.round_header(chat[0], ids[-1]).archive_step == "episode_decision"
            assert repo.latest_round_header(chat[0]).id == ids[-1]
            assert repo.round_dates(chat[0], ids[-2:]) == {ids[-2]: "2026-10-19", ids[-1]: "2026-10-20"}
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)
    assert not any("user_input" in statement or "ai_output" in statement or "rounds.summary" in statement for statement in statements)


@pytest.mark.parametrize("count,required", [(1, False), (6, True)])
def test_summary_to_decision_chain_has_no_extra_model_call(database, chat, count, required):
    ids = seed_rounds(database, chat[0], count, dates=count >= 6)
    with database.transaction() as session:
        repo = Repository(session)
        record = repo.get(Round, ids[-1])
        record.summary, record.archive_step = None, "round_summary"
        record.ai_output = "<content>本回合正文</content>"
        model = repo.add(ModelConfig(chat_id=chat[0], name="摘要模型", api_type="google_generate_content",
                                    base_url="https://provider.test/v1beta", model="test"))
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="round_summary", model_config_id=model.id))
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "本回合摘要"}]}}]})
    async def scenario(client):
        root = f"/api/chats/{chat[0]}/rounds/{ids[-1]}"
        summary = await client.post(root + "/round-summary")
        assert summary.status_code == 200 and summary.json()["archive_step"] == "episode_decision"
        decision = await client.post(root + "/episode-decision")
        assert decision.status_code == 200, decision.text
        assert decision.json()["episode_required"] is required
        with database.transaction() as session:
            repo = ArchiveRepository(session)
            if required:
                with pytest.raises(ConflictError):
                    repo.create_round(chat[0], "下一回合", "输出")
            else:
                assert repo.create_round(chat[0], "下一回合", "输出").round_no == count + 1
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 1
