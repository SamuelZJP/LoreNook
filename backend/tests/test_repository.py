from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.repository.archive import ArchiveRepository
from backend.repository.models import (
    Character, Chat, ChatModelBinding, Definition, Episode, ModelConfig, Round,
    StateSnapshot, UserIdentity, WritingPreset,
)
from backend.repository.queries import Repository
from backend.shared.errors import ConflictError, NotFoundError


def new_round(database, chat_id):
    with database.transaction() as session:
        return ArchiveRepository(session).create_round(chat_id, "用户输入", "<content>正文</content>").id


def through_summary(database, round_id):
    with database.transaction() as session:
        ArchiveRepository(session).save_state(round_id, {"世界": {"日期": "第二天"}, "年龄": 17})
    with database.transaction() as session:
        ArchiveRepository(session).save_summary(round_id, "回合摘要")


def complete_round(database, chat_id):
    round_id = new_round(database, chat_id)
    through_summary(database, round_id)
    with database.transaction() as session:
        ArchiveRepository(session).save_decision(round_id)
    return round_id


def test_connection_enables_foreign_keys(database):
    with database.read() as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 1
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(Character(chat_id="missing-chat", name="无效"))


def test_transaction_rolls_back_entire_bundle(database):
    with pytest.raises(RuntimeError), database.transaction() as session:
        repo = Repository(session)
        chat = repo.add(Chat(title="应回滚"))
        repo.add(Character(chat_id=chat.id, name="应回滚"))
        raise RuntimeError("模拟创建中断")
    with database.read() as session:
        assert session.scalar(select(func.count()).select_from(Chat)) == 0
        assert session.scalar(select(func.count()).select_from(Character)) == 0


def test_read_session_does_not_commit(database):
    with database.read() as session:
        Repository(session).add(Chat(title="不保存"))
    with database.read() as session:
        assert Repository(session).list_chats() == []


def test_library_scope_and_single_chat_owner(database, chat):
    chat_id, _ = chat
    with database.transaction() as session:
        repo = Repository(session)
        repo.add(Character(name="来源一"))
        repo.add(Character(name="来源二"))
        assert len(repo.list_owned(Character, None)) == 2
        assert len(repo.list_owned(Character, chat_id)) == 1
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(Character(chat_id=chat_id, name="第二个角色"))


@pytest.mark.parametrize("owners", ["neither", "both"])
def test_definition_requires_exactly_one_owner(database, chat, owners):
    _, character_id = chat
    with pytest.raises(IntegrityError), database.transaction() as session:
        user_id = session.scalar(select(UserIdentity.id))
        Repository(session).add(Definition(
            character_id=character_id if owners == "both" else None,
            user_identity_id=user_id if owners == "both" else None, content="定义",
        ))


def test_definitions_filter_sort_and_keep_original(database, chat):
    with database.transaction() as session:
        repo = Repository(session)
        repo.add(Definition(character_id=chat[1], order=2, content="{{ state['年龄'] }}", has_template=True))
        repo.add(Definition(character_id=chat[1], order=0, content="停用", enabled=False))
        repo.add(Definition(character_id=chat[1], order=1, content="普通定义"))
    with database.read() as session:
        definitions = Repository(session).definitions(character_id=chat[1], enabled_only=True)
        assert [d.order for d in definitions] == [1, 2]
        assert definitions[1].content == "{{ state['年龄'] }}"


@pytest.mark.parametrize("model", [WritingPreset, ModelConfig])
def test_selected_config_must_belong_to_same_chat(database, chat, model):
    with database.transaction() as session:
        repo = Repository(session)
        other = repo.add(Chat(title="另一个聊天"))
        if model is WritingPreset:
            foreign_id = repo.add(WritingPreset(chat_id=other.id, name="预设", source="源码")).id
        else:
            foreign_id = repo.add(ModelConfig(chat_id=other.id, name="模型", api_type="example",
                                             base_url="https://example.com", model="model")).id
    with pytest.raises(IntegrityError), database.transaction() as session:
        repo = Repository(session)
        if model is WritingPreset:
            repo.get(Chat, chat[0]).writing_preset_id = foreign_id
        else:
            repo.add(ChatModelBinding(chat_id=chat[0], purpose="writing", model_config_id=foreign_id))


def test_initial_and_round_snapshot_uniqueness(database, chat):
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(StateSnapshot(chat_id=chat[0], character_id=chat[1], content={}))
    round_id = new_round(database, chat[0])
    through_summary(database, round_id)
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(StateSnapshot(chat_id=chat[0], character_id=chat[1], round_id=round_id, content={}))


def test_snapshot_cannot_use_foreign_or_library_character(database, chat):
    round_id = new_round(database, chat[0])
    with database.transaction() as session:
        foreign = Repository(session).add(Character(name="来源角色")).id
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(StateSnapshot(chat_id=chat[0], character_id=foreign,
                                              round_id=round_id, content={}))


@pytest.mark.parametrize("content", [[], None, "text", 17])
def test_state_requires_json_object(database, chat, content):
    round_id = new_round(database, chat[0])
    with pytest.raises(IntegrityError), database.transaction() as session:
        ArchiveRepository(session).save_state(round_id, content)
    with database.read() as session:
        assert Repository(session).get(Round, round_id).archive_step == "state_update"


def test_latest_state_uses_round_sequence_and_preserves_json_types(database, chat):
    with database.read() as session:
        assert Repository(session).latest_state(chat[1]).content["年龄"] == 16
    first = complete_round(database, chat[0])
    second = new_round(database, chat[0])
    with database.transaction() as session:
        ArchiveRepository(session).save_state(second, {"值": [None, True, 18, {"中文": "内容"}]})
        initial = session.scalar(select(StateSnapshot).where(StateSnapshot.round_id.is_(None)))
        initial.created_at = datetime.now(UTC) + timedelta(days=30)
    with database.read() as session:
        state = Repository(session).latest_state(chat[1])
        assert state.round_id == second
        assert state.content == {"值": [None, True, 18, {"中文": "内容"}]}
        assert [r.id for r in Repository(session).rounds(chat[0], completed_only=True)] == [first]


def test_state_and_step_rollback_together(database, chat):
    round_id = new_round(database, chat[0])
    with pytest.raises(RuntimeError), database.transaction() as session:
        ArchiveRepository(session).save_state(round_id, {"状态": "新"})
        raise RuntimeError("模拟提交前中断")
    with database.read() as session:
        assert session.scalar(select(StateSnapshot).where(StateSnapshot.round_id == round_id)) is None
        assert Repository(session).get(Round, round_id).archive_step == "state_update"


def test_one_pending_round_repository_and_database(database, chat):
    new_round(database, chat[0])
    with pytest.raises(ConflictError), database.transaction() as session:
        ArchiveRepository(session).create_round(chat[0], "输入", "输出")
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(Round(chat_id=chat[0], round_no=2, user_input="输入", ai_output="输出"))


def test_concurrent_archive_start_only_creates_one_round(database, chat):
    barrier = Barrier(2)

    def attempt():
        barrier.wait(timeout=5)
        try:
            new_round(database, chat[0])
            return "created"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["conflict", "created"]
    with database.read() as session:
        assert [r.round_no for r in Repository(session).rounds(chat[0])] == [1]


def test_error_retry_and_stale_result(database, chat):
    round_id = new_round(database, chat[0])
    with database.transaction() as session:
        ArchiveRepository(session).save_error(round_id, "state_update", "模型调用失败")
    with database.read() as session:
        record = Repository(session).get(Round, round_id)
        assert record.archive_step == "state_update" and record.archive_error == "模型调用失败"
    with database.transaction() as session:
        ArchiveRepository(session).save_state(round_id, {})
    with database.read() as session:
        assert Repository(session).get(Round, round_id).archive_error is None
    with pytest.raises(ConflictError), database.transaction() as session:
        ArchiveRepository(session).save_state(round_id, {"过期": True})


def test_episode_failure_keeps_range_and_does_not_move_boundary(database, chat):
    first = complete_round(database, chat[0])
    second = complete_round(database, chat[0])
    current = new_round(database, chat[0])
    through_summary(database, current)
    with database.transaction() as session:
        ArchiveRepository(session).save_decision(current, start_round_id=first, end_round_id=second)
    with database.transaction() as session:
        ArchiveRepository(session).save_error(current, "episode_summary", "摘要失败")
    with database.read() as session:
        repo = Repository(session)
        assert [r.id for r in repo.unrepresented_rounds(chat[0])] == [first, second, current]
        assert repo.get(Round, current).episode_end_round_id == second
    with pytest.raises(RuntimeError), database.transaction() as session:
        ArchiveRepository(session).save_episode(current, "情节摘要")
        raise RuntimeError("模拟保存中断")
    with database.read() as session:
        assert Repository(session).episodes(chat[0]) == []
        assert Repository(session).get(Round, current).archive_step == "episode_summary"
    with database.transaction() as session:
        ArchiveRepository(session).save_episode(current, "情节摘要")
    with database.read() as session:
        repo = Repository(session)
        assert [r.id for r in repo.unrepresented_rounds(chat[0])] == [current]
        assert repo.episodes(chat[0])[0].created_by_round_id == current
        assert repo.get(Round, current).archive_step == "complete"
        assert repo.get(Round, current).archive_error is None
    with pytest.raises(ConflictError), database.transaction() as session:
        ArchiveRepository(session).save_episode(current, "重复摘要")


def test_episode_must_start_at_first_candidate(database, chat):
    complete_round(database, chat[0])
    second = complete_round(database, chat[0])
    current = new_round(database, chat[0])
    through_summary(database, current)
    with pytest.raises(ConflictError), database.transaction() as session:
        ArchiveRepository(session).save_decision(current, start_round_id=second, end_round_id=second)


def test_delete_chat_cascades_owned_data_and_preserves_library(database, chat):
    first = complete_round(database, chat[0])
    current = new_round(database, chat[0])
    through_summary(database, current)
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_decision(current, start_round_id=first, end_round_id=first)
        repo.save_episode(current, "情节")
        library = repo.add(Character(name="来源"))
        repo.add(Definition(character_id=library.id, content="来源定义"))
        repo.add(Definition(character_id=chat[1], content="聊天定义"))
        preset = repo.add(WritingPreset(chat_id=chat[0], name="预设", source="源码"))
        repo.get(Chat, chat[0]).writing_preset_id = preset.id
        model = repo.add(ModelConfig(chat_id=chat[0], name="模型", api_type="example",
                                     base_url="https://example.com", model="model"))
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="writing", model_config_id=model.id))
    with database.transaction() as session:
        repo = Repository(session)
        repo.delete(repo.get(Chat, chat[0]))
    with database.read() as session:
        for model in (Chat, UserIdentity, WritingPreset, ModelConfig, ChatModelBinding, Round, StateSnapshot, Episode):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(func.count()).select_from(Character)) == 1
        assert session.scalar(select(func.count()).select_from(Definition)) == 1


def test_utc_timestamp_roundtrip_and_missing_record(database, chat):
    with database.read() as session:
        repo = Repository(session)
        assert repo.get(Chat, chat[0]).created_at.tzinfo == UTC
        with pytest.raises(NotFoundError):
            repo.get(Chat, "missing")


@pytest.mark.parametrize("changes", [
    {"archive_step": "unknown"}, {"round_no": 0},
    {"episode_start_round_id": "missing", "episode_end_round_id": "missing"},
    {"archive_step": "episode_summary", "summary": "摘要"},
])
def test_round_constraints(database, chat, changes):
    values = dict(chat_id=chat[0], round_no=1, user_input="输入", ai_output="输出")
    values.update(changes)
    with pytest.raises(IntegrityError), database.transaction() as session:
        Repository(session).add(Round(**values))
