from copy import deepcopy

import pytest

from backend.modules.definitions.renderer import DefinitionRenderer
from backend.modules.definitions.service import DefinitionService
from backend.repository.models import Character, Round, StateSnapshot, UserIdentity
from backend.repository.queries import Repository
from backend.schemas.catalog import DefinitionInput, DefinitionRead
from backend.schemas.definitions import DefinitionPatch, DefinitionReorder
from backend.shared.errors import ConflictError, DefinitionTemplateError, NotFoundError
from backend.workflows.resolve_definitions import resolve_chat_definitions

NAMES = {"user_name": "小明", "character_name": "江清月"}


def definition(content, *, identifier="definition", order=0, enabled=True, template=True):
    return DefinitionRead(id=identifier, character_id="character", user_identity_id=None,
                          content=content, order=order, enabled=enabled, has_template=template)


def test_render_nested_json_conditions_loops_and_preserve_text():
    renderer = DefinitionRenderer()
    state = {"世界": {"日期": "2026-10-19"}, "年龄": 16, "成员": ["甲", "乙"]}
    original_state = deepcopy(state)
    character = [definition("{{ state['世界']['日期'] }}\n{% if state['年龄'] > 10 %}年长{% else %}年幼{% endif %}\n"
                            "{% for name in state['成员'] %}{{ name }}{% endfor %}\n")]
    user = [definition("<content>{{ untouched }}</content>\r\n", identifier="plain", template=False)]
    original_source = character[0].content
    resolved = renderer.resolve(character, user, state, **NAMES)
    assert resolved.character_definitions[0].content == "2026-10-19\n年长\n甲乙\n"
    assert resolved.user_definitions[0].content == "<content>{{ untouched }}</content>\r\n"
    assert character[0].content == original_source and state == original_state


def test_user_and_char_placeholders_in_plain_text_and_templates():
    character = [definition("{{char}}喜欢{{ USER }}，{{ state['年龄'] }}岁，{{ other }}", identifier="plain", template=False),
                 definition("{{char}}喜欢{{ User }}{% if user == '小明' %}！{% endif %}", identifier="template", order=1)]
    resolved = DefinitionRenderer().resolve(character, [], {"年龄": 16}, **NAMES)
    assert [item.content for item in resolved.character_definitions] == [
        "江清月喜欢小明，{{ state['年龄'] }}岁，{{ other }}", "江清月喜欢小明！"]


def test_enabled_filter_deterministic_order_and_plain_invalid_template():
    definitions = [definition("{{ missing }}", identifier="disabled", enabled=False),
                   definition("{{ broken", identifier="b", order=1, template=False),
                   definition("first", identifier="a", order=1, template=False)]
    result = DefinitionRenderer().resolve(definitions, [], {}, **NAMES)
    assert [item.id for item in result.character_definitions] == ["a", "b"]
    assert [item.content for item in result.character_definitions] == ["first", "{{ broken"]


@pytest.mark.parametrize("source", [
    "{{ state['missing'] }}", "{{ state['世界']['missing'] }}", "{{ state['items'] }}",
    "{% if missing %}yes{% endif %}", "{% for item in missing %}{{ item }}{% endfor %}",
    "{% if %}", "{{ 1 / 0 }}", "{{ state['年龄'] + 'text' }}",
    "{% include 'file.txt' %}", "{% import 'file.txt' as other %}",
])
def test_template_errors_identify_definition_and_abort(source):
    with pytest.raises(DefinitionTemplateError) as caught:
        DefinitionRenderer().resolve([definition("valid", identifier="good"), definition(source, identifier="bad")],
                                     [], {"世界": {}, "年龄": 16}, **NAMES)
    assert caught.value.definition_id == "bad" and caught.value.message


def test_template_errors_include_syntax_or_runtime_line():
    for source in ("first\n{% if %}", "first\n{{ state['missing'] }}"):
        with pytest.raises(DefinitionTemplateError) as caught:
            DefinitionRenderer().resolve([definition(source)], [], {}, **NAMES)
        assert caught.value.line == 2


@pytest.mark.parametrize("source", [
    "{{ state.update({'new': 1}) }}", "{{ state['成员'].append('new') }}",
    "{{ state['世界'].clear() }}", "{{ state.__class__.__mro__ }}",
    "{{ cycler.__init__.__globals__.os }}",
])
def test_sandbox_blocks_mutations_and_python_internals(source):
    state = {"世界": {"日期": "2026-10-19"}, "成员": ["甲"]}
    original = deepcopy(state)
    with pytest.raises(DefinitionTemplateError):
        DefinitionRenderer().resolve([definition(source)], [], state, **NAMES)
    assert state == original


def test_raw_tags_are_not_escaped_and_missing_values_can_be_guarded():
    result = DefinitionRenderer().resolve([definition(
        "{{ state['text'] }}|{{ state['missing'] | default('未设置') }}|"
        "{% if state['missing'] is defined %}yes{% else %}no{% endif %}"
    )], [], {"text": "<content>甲 & 乙</content>"}, **NAMES)
    assert result.character_definitions[0].content == "<content>甲 & 乙</content>|未设置|no"


def test_template_context_is_not_reused_and_output_is_bounded():
    renderer = DefinitionRenderer(max_output_chars=5)
    item = definition("{{ state['value'] }}")
    assert renderer.resolve([item], [], {"value": "first"}, **NAMES).character_definitions[0].content == "first"
    assert renderer.resolve([item], [], {"value": "next"}, **NAMES).character_definitions[0].content == "next"
    with pytest.raises(DefinitionTemplateError, match="超过"):
        renderer.resolve([definition("{% for item in range(10) %}a{% endfor %}")], [], {}, **NAMES)


@pytest.mark.parametrize("owner_model", [Character, UserIdentity])
def test_definition_crud_and_reorder_preserve_ids_and_scope(database, owner_model):
    with database.transaction() as session:
        repository = Repository(session)
        owner = repository.add(owner_model(name="来源"))
        owner_field = "character_id" if owner_model is Character else "user_identity_id"
        service = DefinitionService(repository, **{owner_field: owner.id})
        first = service.create(DefinitionInput(content="一", order=10))
        second = service.create(DefinitionInput(content="二", order=10))
        third = service.create(DefinitionInput(content="三", enabled=False))
        updated = service.update(first.id, DefinitionPatch(content="新原文", has_template=True))
        assert updated.id == first.id and updated.order == 10 and updated.enabled is True
        assert service.update(first.id, DefinitionPatch()).content == "新原文"
        reordered = service.reorder(DefinitionReorder(definition_ids=[second.id, first.id, third.id]))
        assert [item.id for item in reordered] == [second.id, first.id, third.id]
        assert [item.order for item in reordered] == [0, 1, 2]
        assert reordered[-1].enabled is False
        other = repository.add(owner_model(name="另一来源"))
        other_service = DefinitionService(repository, **{owner_field: other.id})
        for operation in (lambda: other_service.read(first.id),
                          lambda: other_service.update(first.id, DefinitionPatch(enabled=False)),
                          lambda: other_service.delete(first.id)):
            with pytest.raises(NotFoundError):
                operation()
        service.delete(first.id)
        assert [item.id for item in service.list()] == [second.id, third.id]


def test_incomplete_reorder_rolls_back_and_does_not_touch_records(database):
    with database.transaction() as session:
        repository = Repository(session)
        owner_id = repository.add(Character(name="来源")).id
        service = DefinitionService(repository, character_id=owner_id)
        first = service.create(DefinitionInput(content="一", order=4))
        second = service.create(DefinitionInput(content="二", order=8))
    with pytest.raises(ConflictError), database.transaction() as session:
        DefinitionService(Repository(session), character_id=owner_id).reorder(DefinitionReorder(definition_ids=[first.id]))
    with database.read() as session:
        service = DefinitionService(Repository(session), character_id=owner_id)
        assert [(item.id, item.order) for item in service.list()] == [(first.id, 4), (second.id, 8)]


def test_resolve_chat_uses_current_snapshot_and_keeps_storage_unchanged(database, chat):
    with database.transaction() as session:
        repository = Repository(session)
        character = DefinitionService(repository, character_id=chat[1], chat_id=chat[0])
        character_definition = character.create(DefinitionInput(content="{{ state['年龄'] }}", has_template=True))
        identity_id = repository.list_owned(UserIdentity, chat[0])[0].id
        identity = DefinitionService(repository, user_identity_id=identity_id, chat_id=chat[0])
        identity.create(DefinitionInput(content="{{ state['世界']['日期'] }}", has_template=True))
    initial = resolve_chat_definitions(database, chat[0])
    assert initial.character_definitions[0].content == "16"
    assert initial.user_definitions[0].content == "2026-10-19"
    with database.transaction() as session:
        repository = Repository(session)
        round = repository.add(Round(chat_id=chat[0], round_no=1, user_input="输入", ai_output="输出"))
        snapshot_id = repository.add(StateSnapshot(chat_id=chat[0], character_id=chat[1], round_id=round.id,
                                                   content={"世界": {"日期": "2026-10-20"}, "年龄": 17})).id
    current = resolve_chat_definitions(database, chat[0])
    assert current.state_snapshot_id == snapshot_id != initial.state_snapshot_id
    assert current.character_definitions[0].content == "17"
    assert current.user_definitions[0].content == "2026-10-20"
    with database.read() as session:
        service = DefinitionService(Repository(session), character_id=chat[1], chat_id=chat[0])
        assert service.read(character_definition.id).content == "{{ state['年龄'] }}"


def test_failure_in_user_group_does_not_return_partial_results(database, chat):
    with database.transaction() as session:
        repository = Repository(session)
        DefinitionService(repository, character_id=chat[1], chat_id=chat[0]).create(DefinitionInput(content="成功"))
        identity_id = repository.list_owned(UserIdentity, chat[0])[0].id
        failing = DefinitionService(repository, user_identity_id=identity_id, chat_id=chat[0]).create(
            DefinitionInput(content="{{ missing }}", has_template=True)
        )
    with pytest.raises(DefinitionTemplateError) as caught:
        resolve_chat_definitions(database, chat[0])
    assert caught.value.definition_id == failing.id
