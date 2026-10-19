from backend.tests.state_fixtures import WORLD
import pytest
from sqlalchemy import func, select

from backend.modules.characters.service import CharacterService
from backend.modules.chats.service import ChatService
from backend.modules.state.initial import build_initial_state, empty_schema_state
from backend.modules.users.service import IdentityService
from backend.repository.models import (
    Character, Chat, ChatModelBinding, Definition, ModelConfig, Round, StateSnapshot,
    UserIdentity, WritingPreset,
)
from backend.repository.queries import Repository
from backend.schemas.catalog import CharacterCreate, CharacterPatch, IdentityCreate, IdentityPatch
from backend.schemas.chats import ChatCreate, ChatPatch
from backend.shared.errors import NotFoundError, StateInitializationError
from backend.workflows.create_chat import create_chat


@pytest.fixture
def sources(database):
    with database.transaction() as session:
        repository = Repository(session)
        character = CharacterService(repository, initial_state).create(CharacterCreate(
            name="来源角色", avatar="avatars/character.png", description="角色介绍",
            first_message="<content>开场原文</content>", state_schema="schema source",
            state_reference="参考", state_update_rules="规则",
            definitions=[
                {"order": 2, "content": "{{ state['世界']['日期'] }}", "has_template": True},
                {"order": 0, "content": "停用定义", "enabled": False},
            ],
        ))
        identity = IdentityService(repository).create(IdentityCreate(
            name="来源身份", avatar="avatars/user.png", description="身份介绍",
            definitions=[{"order": 0, "content": "身份定义"}],
        ))
        preset = repository.add(WritingPreset(name="来源预设", source="function build() {}"))
        extra_preset = repository.add(WritingPreset(name="额外预设", source="function parse() {}"))
        model = repository.add(ModelConfig(name="来源模型", api_type="example", base_url="https://example.com",
                                           api_key="credential-for-testing", model="example-model",
                                           default_parameters={"temperature": 0.8, "nested": {"enabled": True}}))
        extra_model = repository.add(ModelConfig(name="备用模型", api_type="example", base_url="https://example.com",
                                                 model="extra-model"))
        return {"character_id": character.id, "user_identity_id": identity.id,
                "writing_preset_id": preset.id, "extra_preset_id": extra_preset.id,
                "model_id": model.id, "extra_model_id": extra_model.id}


def initial_state(schema):
    assert schema == "schema source"
    return {"世界": dict(WORLD), "数字": 16, "布尔": True, "空值": None}


def request_data(sources):
    return dict(
        title="新聊天", character_id=sources["character_id"], user_identity_id=sources["user_identity_id"],
        writing_preset_id=sources["writing_preset_id"],
        writing_preset_ids=[sources["extra_preset_id"], sources["writing_preset_id"], sources["extra_preset_id"]],
        model_config_ids=[sources["extra_model_id"], sources["model_id"]],
        model_bindings={purpose: sources["model_id"] for purpose in (
            "writing", "state_update", "round_summary", "episode_summary"
        )},
        recent_rounds=3, min_summaries=4,
    )


def table_counts(database):
    with database.read() as session:
        return {model.__tablename__: session.scalar(select(func.count()).select_from(model)) for model in (
            Chat, Character, UserIdentity, Definition, WritingPreset, ModelConfig, ChatModelBinding, StateSnapshot, Round
        )}


def test_create_copies_everything_rebuilds_links_and_deduplicates(database, sources):
    result = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    assert result.character.id != sources["character_id"]
    assert result.user_identity.id != sources["user_identity_id"]
    assert result.character.chat_id == result.user_identity.chat_id == result.id
    assert result.character.first_message == "<content>开场原文</content>"
    assert result.character.state_schema == "schema source"
    assert result.character.state_reference == "参考"
    assert result.character.state_update_rules == "规则"
    assert result.recent_rounds == 3 and result.min_summaries == 4
    assert [item.order for item in result.character.definitions] == [0, 2]
    assert result.character.definitions[0].enabled is False
    assert result.character.definitions[1].has_template is True
    assert result.character.definitions[1].content == "{{ state['世界']['日期'] }}"
    assert all(item.character_id == result.character.id and item.user_identity_id is None
               for item in result.character.definitions)
    assert result.user_identity.definitions[0].user_identity_id == result.user_identity.id
    assert result.latest_state.round_id is None
    assert result.latest_state.character_id == result.character.id
    assert result.latest_state.content == initial_state("schema source")
    assert len(result.writing_presets) == 2 and len(result.model_configs) == 2
    assert result.writing_preset_id in {preset.id for preset in result.writing_presets}
    assert result.writing_preset_id != sources["writing_preset_id"]
    assert len(set(result.model_bindings.values())) == 1
    assert result.model_bindings["writing"] != sources["model_id"]
    assert "credential-for-testing" not in result.model_dump_json()
    with database.read() as session:
        repository = Repository(session)
        assert repository.rounds(result.id) == []  # First Message is not a formal round.
        config = repository.get(ModelConfig, result.model_bindings["writing"])
        assert config.api_key == "credential-for-testing"
        assert config.default_parameters == {"temperature": 0.8, "nested": {"enabled": True}}
        source_definitions = repository.definitions(character_id=sources["character_id"])
        assert {item.id for item in source_definitions}.isdisjoint({item.id for item in result.character.definitions})


def test_sources_and_two_chats_are_independent_even_after_source_deletion(database, sources):
    first = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    second = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    with database.transaction() as session:
        repository = Repository(session)
        CharacterService(repository).update(sources["character_id"], CharacterPatch(name="修改来源", definitions=[]))
        CharacterService(repository).update(first.character.id, CharacterPatch(first_message="聊天一开场"), first.id)
        IdentityService(repository).update(first.user_identity.id, IdentityPatch(name="聊天一身份"), first.id)
        config = repository.get(ModelConfig, sources["model_id"])
        config.default_parameters = {"nested": {"enabled": False}}
        repository.get(WritingPreset, sources["writing_preset_id"]).source = "修改源码"
        CharacterService(repository).delete_source(sources["character_id"])
        IdentityService(repository).delete_source(sources["user_identity_id"])
        repository.delete(repository.get(ModelConfig, sources["model_id"]))
        repository.delete(repository.get(WritingPreset, sources["writing_preset_id"]))
    with database.read() as session:
        service = ChatService(Repository(session))
        current_first, current_second = service.detail(first.id), service.detail(second.id)
        assert current_first.character.first_message == "聊天一开场"
        assert current_first.user_identity.name == "聊天一身份"
        assert current_second.character.first_message == "<content>开场原文</content>"
        assert current_second.user_identity.name == "来源身份"
        assert current_first.character.name == current_second.character.name == "来源角色"
        assert len(current_first.character.definitions) == len(current_second.character.definitions) == 2
        assert current_first.latest_state.id != current_second.latest_state.id
        assert all(config.default_parameters.get("nested", {}).get("enabled", True) for config in current_second.model_configs)


@pytest.mark.parametrize("missing_field", ["character_id", "user_identity_id", "writing_preset_id", "model_bindings"])
def test_missing_source_rolls_back_entire_bundle(database, sources, missing_field):
    data = request_data(sources)
    if missing_field == "model_bindings":
        data[missing_field] = {"writing": "missing"}
    else:
        data[missing_field] = "missing"
    before = table_counts(database)
    with pytest.raises(NotFoundError):
        create_chat(database, ChatCreate(**data), initial_state)
    assert table_counts(database) == before


def test_chat_copy_cannot_be_used_as_a_library_source(database, sources):
    first = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    for field, value in (("character_id", first.character.id), ("user_identity_id", first.user_identity.id),
                         ("writing_preset_id", first.writing_preset_id)):
        data = request_data(sources) | {field: value}
        before = table_counts(database)
        with pytest.raises(NotFoundError):
            create_chat(database, ChatCreate(**data), initial_state)
        assert table_counts(database) == before


@pytest.mark.parametrize("state", [[], "text", None, {"bad": float("nan")}, {"bad": float("inf")}])
def test_invalid_initial_state_rolls_back_copied_data(database, sources, state):
    before = table_counts(database)
    with pytest.raises(StateInitializationError):
        create_chat(database, ChatCreate(**request_data(sources)), lambda _: state)
    assert table_counts(database) == before


def test_initial_state_provider_failure_rolls_back(database, sources):
    def failing_provider(_):
        raise RuntimeError("runtime failure")
    before = table_counts(database)
    with pytest.raises(RuntimeError, match="runtime failure"):
        create_chat(database, ChatCreate(**request_data(sources)), failing_provider)
    assert table_counts(database) == before


def test_default_provider_only_accepts_empty_schema():
    with pytest.raises(StateInitializationError, match="世界"):
        build_initial_state(empty_schema_state, " \n ")
    with pytest.raises(StateInitializationError):
        build_initial_state(empty_schema_state, "some schema")
    original = {"世界": dict(WORLD)}
    saved = build_initial_state(lambda _: original, "schema")
    original["世界"]["日期"] = "修改"
    assert saved["世界"]["日期"] == "2026-10-19"


def test_chat_configuration_only_uses_local_ids_and_updates_atomically(database, sources):
    first = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    second = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    for changes in ({"writing_preset_id": second.writing_preset_id}, {"model_bindings": second.model_bindings}):
        with pytest.raises(NotFoundError), database.transaction() as session:
            ChatService(Repository(session)).update(first.id, ChatPatch(title="应回滚", **changes))
    with database.transaction() as session:
        result = ChatService(Repository(session)).update(first.id, ChatPatch(
            title="修改聊天", recent_rounds=0, min_summaries=0,
            writing_preset_id=None, model_bindings={},
        ))
        assert result.title == "修改聊天" and result.writing_preset_id is None
        assert result.model_bindings == {} and result.recent_rounds == result.min_summaries == 0
        assert len(result.model_configs) == 2


def test_delete_chat_keeps_other_chat_and_library(database, sources):
    first = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    second = create_chat(database, ChatCreate(**request_data(sources)), initial_state)
    with database.transaction() as session:
        ChatService(Repository(session)).delete(first.id)
    with database.read() as session:
        repository = Repository(session)
        assert len(ChatService(repository).list()) == 1
        assert ChatService(repository).detail(second.id).id == second.id
        assert repository.get_owned(Character, sources["character_id"], None).name == "来源角色"
        assert len(repository.definitions(character_id=sources["character_id"])) == 2
