import json

import httpx
import pytest

from backend.modules.memory.layout import expand_layout, plan_layout, validate_layout
from backend.modules.memory.render import render_episode, render_materials, render_round
from backend.modules.memory.service import MemoryService
from backend.modules.memory.sources import MemorySources
from backend.modules.presets.runtime import PresetRuntime
from backend.recall.errors import RecallError
from backend.recall.judge import parse_ids
from backend.recall.models import ChatRecallSettings
from backend.recall.prompts import SYSTEM
from backend.repository.models import Definition, ModelConfig
from backend.repository.queries import Repository
from backend.schemas.memory import MemoryLayout, MemorySettings
from backend.schemas.presets import WritingMaterials
from backend.shared.errors import ConflictError
from backend.tests.test_catalog_api import run_api
from backend.tests.test_memory import episode, rounds, seed_history
from backend.tests.test_writing import EXAMPLE, writing_chat  # noqa: F401

SETTINGS = MemorySettings(recent_rounds=2, min_summaries=3)


def planned():
    sources = MemorySources.build(rounds(14), [episode(1, 3), episode(4, 6), episode(7, 9)])
    return plan_layout(sources, SETTINGS), sources


def shape(layout):
    return [(segment.kind, segment.numbers) for segment in layout.memory]


def test_expansion_only_refines_in_place():
    layout, sources = planned()
    assert shape(layout) == [("episode", [1, 2, 3]), ("summary", [10, 11, 12])]
    opened = expand_layout(layout, sources, episodes={2})
    assert shape(opened) == [("episode", [1]), ("summary", [4, 5, 6]), ("episode", [3]), ("summary", [10, 11, 12])]
    expanded = expand_layout(opened, sources, summaries={5, 11})
    assert shape(expanded) == [
        ("episode", [1]), ("summary", [4]), ("round", [5]), ("summary", [6]), ("episode", [3]),
        ("summary", [10]), ("round", [11]), ("summary", [12]),
    ]
    assert expanded.recent_rounds == layout.recent_rounds == [13, 14]
    assert shape(layout)[0] == ("episode", [1, 2, 3]), "the input layout is not changed"
    validate_layout(expanded, layout, sources)


def test_rendered_memory_keeps_order_and_uses_the_round_structure():
    layout, sources = planned()
    text = render_materials(expand_layout(layout, sources, summaries={11}), sources, "小明").memory
    round_text = "\n\n<小明>\n输入11\n</小明>\n\n<plot>\n正文11\n</plot>\n\n"
    assert text.index("摘要10") < text.index(round_text) < text.index("摘要12")
    assert "<think>" not in text and "摘要11" not in text


def test_rendered_round_has_a_time_and_place_header():
    record = rounds(1)[0].model_copy(update={"world": {"日期": "2024-11-14", "星期": "星期四", "时间": "17:53", "地点": "校门外"}})
    assert render_round(record, "小明") == "2024-11-14—17:53—校门外\n\n<小明>\n输入1\n</小明>\n\n<plot>\n正文1\n</plot>"


def test_rendered_round_leaves_out_what_is_empty():
    record = rounds(1)[0].model_copy(update={"user_input": " \n", "world": {"日期": "2024-11-14", "时间": "17:53", "地点": ""}})
    assert render_round(record, "小明") == "2024-11-14—17:53\n\n<plot>\n正文1\n</plot>"
    assert render_round(rounds(1)[0], "小明") == "<小明>\n输入1\n</小明>\n\n<plot>\n正文1\n</plot>", "no world, no header"


@pytest.mark.parametrize("title,summary,expected", [
    ("初访图书馆", " 2026/10/19—图书馆\r\n正文\n第二段\n", "2026/10/19—图书馆\n【初访图书馆】\n正文\n第二段"),
    ("初访图书馆", "2026/10/19—图书馆。正文", "【初访图书馆】\n2026/10/19—图书馆。正文"),
    ("", " 2026/10/19—图书馆\n正文\n", " 2026/10/19—图书馆\n正文\n"),
])
def test_unexpanded_episode_shows_its_title_below_the_header(title, summary, expected):
    record = episode(1, 3).model_copy(update={"title": title, "summary": summary})
    assert render_episode(record) == expected


def test_episode_title_reaches_the_rendered_memory():
    records = [episode(1, 3).model_copy(update={"title": "标题", "summary": "2026/10/19—某地\n情节"})]
    sources = MemorySources.build(rounds(14), records)
    text = render_materials(plan_layout(sources, SETTINGS), sources, "小明").memory
    assert text.startswith("2026/10/19—某地\n【标题】\n情节\n")


def test_adjacent_expanded_rounds_are_separated_by_one_blank_line():
    layout, sources = planned()
    text = render_materials(expand_layout(layout, sources, summaries={10, 11}), sources, "小明").memory
    assert "<plot>\n正文10\n</plot>\n\n<小明>\n输入11" in text


def test_round_without_valid_content_tag_keeps_its_text():
    records = rounds(4)
    records[0].ai_output = "手工改过的正文"
    sources = MemorySources.build(records, [])
    layout = plan_layout(sources, MemorySettings(recent_rounds=1, min_summaries=0))
    text = render_materials(expand_layout(layout, sources, summaries={1}), sources, "小明").memory
    assert "<plot>\n手工改过的正文\n</plot>" in text


@pytest.mark.parametrize("memory,recent", [
    ([{"kind": "summary", "numbers": [10, 11, 12]}], [13, 14]),  # rounds missing
    ([{"kind": "episode", "numbers": [1, 2, 3, 4]}, {"kind": "summary", "numbers": [10, 11, 12]}], [13, 14]),  # no such episode
    ([{"kind": "episode", "numbers": [2, 1, 3]}, {"kind": "summary", "numbers": [10, 11, 12]}], [13, 14]),  # out of order
    ([{"kind": "episode", "numbers": [1, 2, 3]}, {"kind": "summary", "numbers": [10, 11, 12, 13]}], [14]),  # recent changed
    ([{"kind": "episode", "numbers": [1, 2, 3]}, {"kind": "summary", "numbers": [10, 11, 12, 99]}], [13, 14]),  # no such round
])
def test_layout_that_no_longer_fits_is_a_conflict(memory, recent):
    layout, sources = planned()
    with pytest.raises(ConflictError):
        validate_layout(MemoryLayout(memory=memory, recent_rounds=recent), layout, sources)


def test_example_preset_needs_no_change_for_expanded_rounds():
    layout, sources = planned()
    materials = WritingMaterials(first_message="开场", character_name="角色", user_identity_name="我", user_input="输入", state={},
                                 **render_materials(expand_layout(layout, sources, summaries={11}), sources, "我").model_dump())
    contents = PresetRuntime().build(EXAMPLE, materials).body["contents"]
    assert "<plot>\n正文11\n</plot>" in contents[2]["parts"][0]["text"]
    assert len(contents) == 6 + 2 * 2, "only recent rounds are dialogue turns"


@pytest.mark.parametrize("text,expected", [
    ('{"reason": "无", "ids": []}', []),
    ('```json\n{"reason": "有", "ids": ["E1", "R2"]}\n```', ["E1", "R2"]),
])
def test_parse_ids(text, expected):
    assert parse_ids(text) == expected


@pytest.mark.parametrize("text", ["不是JSON", "[]", '{"reason": "缺结论"}', '{"ids": "E1"}', '{"ids": [1]}'])
def test_parse_ids_rejects_unusable_output(text):
    with pytest.raises(RecallError):
        parse_ids(text)


def enable(database, chat_id, depth=2, **limits):
    with database.transaction() as session:
        repo = Repository(session)
        model = repo.add(ModelConfig(chat_id=chat_id, name="召回", api_type="deepseek_chat_completions",
                                     base_url="https://recall.test", api_key="k", model="recall-model",
                                     default_parameters={}))
        repo.add(ChatRecallSettings(chat_id=chat_id, enabled=True, model_config_id=model.id, depth=depth, **limits))
        # The fixture's template reads a field the seeded state doesn't have.
        for definition in session.query(Definition).filter(Definition.has_template.is_(True), Definition.enabled.is_(True)):
            definition.content = "序号{{ state['序号'] }}"


def handler_for(prompts, answers, writes):
    def handler(request):
        body = json.loads(request.content)
        if "messages" not in body:
            writes.append(json.loads(body["contents"][0]["parts"][0]["text"]))
            return httpx.Response(200, json={"text": "<content>正文</content>"})
        system, prompt = (message["content"] for message in body["messages"])
        assert system == SYSTEM
        prompts.append(prompt)
        content = json.dumps({"reason": "理由", "ids": answers[len(prompts) - 1]})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
                                                      "message": {"role": "assistant", "content": content}}]})
    return handler


def test_two_passes_expand_and_writing_uses_the_layout(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id)
    with database.read() as session:
        baseline = MemoryService(Repository(session)).timeline(chat_id)
    prompts, writes = [], []
    # Seeded episodes cover rounds 1-4 and 5-8. The made-up label is skipped; the repeat counts once.
    answers = [["E2", "E99", "E2"], ["R6", "R9"]]

    async def scenario(client):
        root = f"/api/chats/{chat_id}"
        request = {"user_input": "你当时怎么说的", "instruction": "必须提到初见"}
        response = await client.post(root + "/recall", json=request)
        assert response.status_code == 200, response.text
        result = response.json()
        assert [(s["kind"], s["numbers"]) for s in result["layout"]["memory"]] == [
            ("episode", [1]), ("summary", [5]), ("round", [6]), ("summary", [7, 8]), ("round", [9]),
            ("summary", list(range(10, 16))),
        ]
        assert result["layout"]["recent_rounds"] == [16, 17, 18, 19, 20]
        assert [item["kind"] for item in result["timeline"]["items"]][:4] == ["episode", "summary", "round", "summary"]
        write = await client.post(root + "/writing", json={**request, "layout": result["layout"]})
        assert write.status_code == 200, write.text
        assert "2026-10-19—06:00—教室\n\n<" in writes[0]["memory"] and "<plot>\n6\n</plot>" in writes[0]["memory"]
        assert "<plot>\n9\n</plot>" in writes[0]["memory"]
        assert [item["round_no"] for item in writes[0]["recent_rounds"]] == [16, 17, 18, 19, 20]
        preview = await client.post(root + "/writing-preview", json={**request, "layout": result["layout"]})
        assert "<plot>\n6\n</plot>" in json.loads(preview.json()["request"]["body"]["contents"][0]["parts"][0]["text"])["memory"]
        memory = await client.get(root + "/memory")
        assert memory.json()["items"] == json.loads(baseline.model_dump_json())["items"], "recall is not saved"

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler_for(prompts, answers, writes)))
    assert len(prompts) == 2
    first, second = prompts
    assert "[E1]" in first and "[E2]" in first and "[R" not in first
    assert "[E" not in second and "[R5]" in second and "[R9]" in second, "expanded and original summaries are both judged"
    for prompt in prompts:
        assert "必须提到初见" in prompt and "你当时怎么说的" in prompt
        assert "<plot>\n19\n</plot>" in prompt and "<plot>\n20\n</plot>" in prompt and "<plot>\n18\n</plot>" not in prompt, "depth is 2"
        assert "2026-10-19—20:00—教室" in prompt
        assert "序号" not in prompt, "only the header's fields of the state reach the basis"
    assert "拿不准时不选" in second and "拿不准时不选" not in first
    assert "最多选择 2 个情节" in first and "最多选择 5 个摘要" in second


def recall_shape(database, chat_id, answers, prompts=None):
    prompts = [] if prompts is None else prompts
    shapes = []

    async def scenario(client):
        response = await client.post(f"/api/chats/{chat_id}/recall", json={"user_input": "输入"})
        assert response.status_code == 200, response.text
        shapes.extend((s["kind"], s["numbers"]) for s in response.json()["layout"]["memory"])

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler_for(prompts, answers, [])))
    return shapes


def test_results_over_the_limit_keep_the_first_items_in_the_models_order(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id, episode_limit=1, summary_limit=2)
    prompts = []
    # Made-up labels and repeats don't use up the limit. E2 comes first, so E1 is dropped.
    shapes = recall_shape(database, chat_id, [["E99", "E2", "E2", "E1"], ["R12", "R99", "R6", "R9"]], prompts)
    assert shapes == [("episode", [1]), ("summary", [5]), ("round", [6]), ("summary", [7, 8, 9, 10, 11]),
                      ("round", [12]), ("summary", [13, 14, 15])]
    assert "最多选择 1 个情节" in prompts[0] and "最多选择 2 个摘要" in prompts[1]
    assert "最多 1 个" in prompts[0] and "最多 2 个" in prompts[1]


def test_zero_limit_skips_that_pass(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id, episode_limit=0)
    prompts = []
    shapes = recall_shape(database, chat_id, [["R9"]], prompts)
    assert len(prompts) == 1 and "[R9]" in prompts[0] and "[E" not in prompts[0]
    assert shapes[0] == ("episode", [1, 2]) and ("round", [9]) in shapes


def test_switch_off_makes_no_model_call_even_with_a_model(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id)
    with database.transaction() as session:
        session.get(ChatRecallSettings, chat_id).enabled = False
    prompts = []
    assert recall_shape(database, chat_id, [], prompts)[0] == ("episode", [1, 2])
    assert prompts == []


def test_depth_zero_uses_only_the_latest_input(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id, depth=0)
    prompts = []

    async def scenario(client):
        assert (await client.post(f"/api/chats/{chat_id}/recall", json={"user_input": "输入"})).status_code == 200

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler_for(prompts, [[], []], [])))
    assert "<plot>" not in prompts[0] and "最新输入：输入" in prompts[0]


def test_depth_can_exceed_recent_rounds(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id, depth=7)
    prompts = []

    async def scenario(client):
        assert (await client.post(f"/api/chats/{chat_id}/recall", json={"user_input": "输入"})).status_code == 200

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler_for(prompts, [[], []], [])))
    assert "<plot>\n14\n</plot>" in prompts[0] and "<plot>\n13\n</plot>" not in prompts[0]


def test_off_means_no_model_call_and_the_assembled_layout(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)

    def handler(request):
        raise AssertionError("no model call expected")

    async def scenario(client):
        root = f"/api/chats/{chat_id}"
        assert (await client.get(root + "/recall-settings")).json() == {
            "enabled": False, "model_config_id": None, "depth": 3, "episode_limit": 2, "summary_limit": 5}
        result = (await client.post(root + "/recall", json={"user_input": "输入"})).json()
        assert result["timeline"]["items"] == (await client.get(root + "/memory")).json()["items"]

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_pass_without_candidates_makes_no_call(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    enable(database, chat_id)
    prompts = []

    async def scenario(client):
        response = await client.post(f"/api/chats/{chat_id}/recall", json={"user_input": "输入"})
        assert response.status_code == 200, response.text

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler_for(prompts, [], [])))
    assert prompts == []


def test_unusable_response_is_422_and_stale_layout_is_409(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]
    seed_history(database, chat_id)
    enable(database, chat_id)

    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
                                                      "message": {"role": "assistant", "content": "不是JSON"}}]})

    async def scenario(client):
        root = f"/api/chats/{chat_id}"
        assert (await client.post(root + "/recall", json={"user_input": "输入"})).status_code == 422
        stale = {"user_input": "输入", "layout": {"memory": [], "recent_rounds": [1]}}
        assert (await client.post(root + "/writing", json=stale)).status_code == 409
        assert (await client.post(root + "/writing-preview", json=stale)).status_code == 409

    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_settings_validate_their_model_and_chat_deletion_removes_them(database, writing_chat):  # noqa: F811
    chat_id = writing_chat["chat_id"]

    async def scenario(client):
        root = f"/api/chats/{chat_id}"
        assert (await client.put(root + "/recall-settings", json={"model_config_id": "missing"})).status_code == 404
        assert (await client.put(root + "/recall-settings", json={"depth": -1})).status_code == 422
        assert (await client.put(root + "/recall-settings", json={"episode_limit": -1})).status_code == 422
        assert (await client.put(root + "/recall-settings", json={"summary_limit": -1})).status_code == 422
        library = await client.post("/api/model-configs", json={
            "name": "库模型", "api_type": "google_generate_content", "base_url": "https://x.test/v1beta", "model": "m"})
        assert library.status_code == 201, library.text
        setup = await client.post(root + "/recall-setup", json={"enabled": True, "model_config_id": library.json()["id"], "depth": 5})
        assert setup.status_code == 200, setup.text
        own = setup.json()["model_config_id"]
        assert own != library.json()["id"] and setup.json()["depth"] == 5 and setup.json()["enabled"] is True
        assert (await client.get(root + "/recall-settings")).json() == setup.json()
        assert (await client.delete(root)).status_code == 204

    run_api(database, scenario)
    with database.read() as session:
        assert session.get(ChatRecallSettings, chat_id) is None
