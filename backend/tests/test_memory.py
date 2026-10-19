import pytest
from pydantic import ValidationError

from backend.modules.memory.assembler import assemble_memory
from backend.modules.memory.service import MemoryService
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Chat
from backend.repository.queries import Repository
from backend.schemas.memory import ArchivedRound, EpisodeMemory, MemoryHistory
from backend.shared.errors import ConflictError
from backend.tests.test_catalog_api import run_api


def rounds(count):
    return [ArchivedRound(id=f"r{i}", round_no=i, user_input=f" 输入{i}\r\n",
                          ai_output=f"<think>保留{i}</think>\r\n<content>正文{i}</content>\n",
                          summary=f" 摘要{i}\r\n") for i in range(1, count + 1)]


def episode(start, end):
    return EpisodeMemory(id=f"e{start}", start_round_id=f"r{start}", end_round_id=f"r{end}",
                         start_round_no=start, end_round_no=end, summary=f" 情节{start}—{end}\r\n")


def select(count, x, y, ranges=()):
    return assemble_memory(rounds(count), [episode(*pair) for pair in ranges],
                           recent_rounds=x, min_summaries=y)


def coverage(history):
    return [number for item in history.items for number in
            (range(item.start_round_no, item.end_round_no + 1)
             if item.kind == "episode" else [item.round_no])]


@pytest.mark.parametrize("count,x,y,summary_count,full_count", [
    (0, 5, 6, 0, 0), (3, 5, 6, 0, 3), (5, 5, 6, 0, 5),
    (6, 5, 6, 1, 5), (11, 5, 6, 6, 5), (20, 5, 6, 15, 5),
    (4, 0, 6, 4, 0), (4, 0, 0, 4, 0), (4, 2, 0, 2, 2),
])
def test_without_episodes_keeps_all_history(count, x, y, summary_count, full_count):
    result = select(count, x, y)
    assert result.total_rounds == count
    assert [item.kind for item in result.items] == ["summary"] * summary_count + ["round"] * full_count
    assert coverage(result) == list(range(1, count + 1))
    assert result.uses_compressed_history == (summary_count > 0)


def test_design_example_and_serializable_contract():
    result = select(20, 5, 6, [(1, 4), (5, 8), (9, 12)])
    assert [item.id for item in result.items[:2]] == ["e1", "e5"]
    assert [item.round_no for item in result.items if item.kind == "summary"] == list(range(9, 16))
    assert [item.round_no for item in result.items if item.kind == "round"] == list(range(16, 21))
    assert coverage(result) == list(range(1, 21))
    payload = result.model_dump()
    assert payload.pop("uses_compressed_history") is True
    assert MemoryHistory.model_validate(payload) == result


@pytest.mark.parametrize("count,x,y,ranges,selected_ids", [
    (20, 5, 7, [(1, 4), (5, 8), (9, 12)], ["e1", "e5"]),  # exactly Y
    (10, 2, 2, [(1, 7), (8, 8)], []),  # cannot skip a large episode
    (10, 3, 0, [(1, 4), (5, 8), (9, 9)], ["e1"]),  # cannot split across X
    (10, 10, 0, [(1, 4)], []),
    (10, 0, 0, [(1, 4), (5, 10)], ["e1", "e5"]),
    (10, 0, 6, [(1, 4), (5, 8)], ["e1"]),
    (10, 3, 20, [(1, 4)], []),
    (10, 2, 2, [(2, 3), (5, 6)], ["e2", "e5"]),  # uncovered gaps keep summaries
])
def test_folding_boundaries(count, x, y, ranges, selected_ids):
    result = select(count, x, y, ranges)
    assert [item.id for item in result.items if item.kind == "episode"] == selected_ids
    assert coverage(result) == list(range(1, count + 1))
    assert len([item for item in result.items if item.kind == "round"]) == min(count, x)
    if selected_ids:
        assert len([item for item in result.items if item.kind == "summary"]) >= y


def test_sort_by_round_sequence_preserve_text_and_input_objects():
    source_rounds = rounds(10)
    source_episodes = [episode(5, 6), episode(1, 4)]
    original = [record.model_dump() for record in source_rounds + source_episodes]
    result = assemble_memory(list(reversed(source_rounds)), source_episodes,
                             recent_rounds=2, min_summaries=2)
    assert coverage(result) == list(range(1, 11))
    assert result.items[0].summary == source_episodes[1].summary
    assert result.items[2].summary == source_rounds[6].summary
    assert result.items[-1].user_input == source_rounds[-1].user_input
    assert result.items[-1].ai_output == source_rounds[-1].ai_output
    result.items[0].summary = "只修改返回对象"
    assert [record.model_dump() for record in source_rounds + source_episodes] == original


@pytest.mark.parametrize("ranges", [[(1, 4), (4, 6)], [(4, 2)], [(1, 11)], [(1, 4), (1, 4)]])
def test_reject_invalid_saved_ranges_even_when_not_selected(ranges):
    with pytest.raises(ConflictError):
        select(10, 10, 6, ranges)


def test_reject_missing_round_inside_episode_and_mismatched_endpoint():
    source = rounds(10)
    with pytest.raises(ConflictError):
        assemble_memory(source[:2] + source[3:], [episode(1, 5)], recent_rounds=2, min_summaries=0)
    invalid = episode(1, 5).model_copy(update={"end_round_id": "r6"})
    with pytest.raises(ConflictError):
        assemble_memory(source, [invalid], recent_rounds=2, min_summaries=0)


@pytest.mark.parametrize("bad", [-1, True, 1.5, "5"])
def test_reject_invalid_memory_settings(bad):
    for field in ("recent_rounds", "min_summaries"):
        settings = {"recent_rounds": 5, "min_summaries": 6, field: bad}
        with pytest.raises(ValidationError):
            assemble_memory([], [], **settings)


def test_missing_summary_is_error_only_if_used():
    source = rounds(3)
    source[0].summary = None
    with pytest.raises(ConflictError):
        assemble_memory(source, [], recent_rounds=1, min_summaries=0)
    assert assemble_memory(source, [episode(1, 2)], recent_rounds=1, min_summaries=0).items[0].kind == "episode"
    assert not assemble_memory(source, [], recent_rounds=3, min_summaries=0).uses_compressed_history


def seed_history(database, chat_id):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        ids = []
        for number in range(1, 21):
            record = repo.create_round(chat_id, f" 输入{number}\r\n",
                                       f"<think>思考</think>\r\n<content>{number}</content>\n")
            ids.append(record.id)
            repo.save_state(record.id, {"序号": number})
            repo.save_summary(record.id, f" 摘要{number}\r\n")
            if number in (5, 9, 13):
                repo.save_decision(record.id, start_round_id=ids[number - 5], end_round_id=ids[number - 2])
                repo.save_episode(record.id, f" 情节{number}\r\n")
            else:
                repo.save_decision(record.id)
    return ids


def test_service_and_http_use_chat_settings_preserve_database_and_exclude_pending(database, chat):
    ids = seed_history(database, chat[0])
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        pending = repo.create_round(chat[0], "未归档输入", "未归档输出")
        repo.save_state(pending.id, {"序号": 21})
        repo.save_summary(pending.id, "未归档摘要")
        other = repo.add(Chat(title="其他聊天", recent_rounds=0, min_summaries=0)).id
        foreign = repo.create_round(other, "其他聊天输入", "其他聊天输出")
        # Direct fixture for another chat's completed history; no state is needed for selection.
        foreign.summary, foreign.episode_required, foreign.archive_step = "其他摘要", False, "complete"
        session.flush()
        before = [(r.id, r.user_input, r.ai_output, r.summary, r.archive_step, r.archive_error)
                  for r in repo.rounds(chat[0])]
        episode_before = [(e.id, e.summary) for e in repo.episodes(chat[0])]

    async def scenario(client):
        path = f"/api/chats/{chat[0]}/memory"
        response = await client.get(path)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["chat_id"] == chat[0] and payload["total_rounds"] == 20
        assert payload["uses_compressed_history"] is True
        assert [item["kind"] for item in payload["items"]] == ["episode"] * 2 + ["summary"] * 7 + ["round"] * 5
        assert payload["items"][-1]["ai_output"] == "<think>思考</think>\r\n<content>20</content>\n"
        assert payload["items"][-1]["id"] == ids[-1]
        assert (await client.get("/api/chats/missing/memory")).status_code == 404
        assert (await client.get(f"/api/chats/{other}/memory")).json()["total_rounds"] == 1
        updated = await client.patch(f"/api/chats/{chat[0]}", json={"recent_rounds": 20, "min_summaries": 0})
        assert updated.status_code == 200
        fresh = (await client.get(path)).json()
        assert fresh["uses_compressed_history"] is False
        assert len(fresh["items"]) == 20 and all(item["kind"] == "round" for item in fresh["items"])
    run_api(database, scenario)

    with database.read() as session:
        repo = Repository(session)
        assert [(r.id, r.user_input, r.ai_output, r.summary, r.archive_step, r.archive_error)
                for r in repo.rounds(chat[0])] == before
        assert [(e.id, e.summary) for e in repo.episodes(chat[0])] == episode_before
        result = MemoryService(repo).assemble(chat[0])
    assert result.total_rounds == 20  # independent of the closed Session


def test_empty_chat_and_http_conflict_on_corrupt_episode(database, chat):
    with database.read() as session:
        result = MemoryService(Repository(session)).assemble(chat[0])
        assert result.items == [] and result.uses_compressed_history is False
    seed_history(database, chat[0])
    with database.transaction() as session:
        repo = Repository(session)
        second = repo.episodes(chat[0])[1]
        second.start_round_id = repo.rounds(chat[0])[2].id  # overlap first episode
    async def scenario(client):
        assert (await client.get(f"/api/chats/{chat[0]}/memory")).status_code == 409
    run_api(database, scenario)
