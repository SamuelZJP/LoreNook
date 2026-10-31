from backend.tests.state_fixtures import STATE_SCHEMA
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from backend.modules.memory.layout import plan_layout
from backend.modules.memory.render import render_materials
from backend.modules.memory.sources import MemorySources
from backend.modules.presets.runtime import PresetRuntime
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Character, Chat, Definition, WritingPreset
from backend.repository.queries import Repository
from backend.schemas.memory import ArchivedRound, EpisodeMemory, MemorySettings
from backend.schemas.presets import WritingMaterials
from backend.shared.errors import PresetExecutionError
from backend.tests.test_catalog_api import run_api

EXAMPLE = (Path(__file__).parents[1] / "modules/presets/examples/google_tool.js").read_text(encoding="utf-8")
SIMPLE = """
function build(m) {return {api_type: 'example', body: {text: m.user_input, state: m.state}};}
function parse(r) {return r.text;}
"""


def materials(count=0, x=5, y=6, episodes=()):
    rounds = [ArchivedRound(id=f"r{i}", round_no=i, user_input=f"用户{i}",
                            ai_output=f"<report_nya~>报告{i}</report_nya~><content>正文{i}</content>",
                            summary=f"摘要{i}") for i in range(1, count + 1)]
    ranges = [EpisodeMemory(id=f"e{start}", start_round_id=f"r{start}", end_round_id=f"r{end}",
                            start_round_no=start, end_round_no=end, summary=f"情节{start}")
              for start, end in episodes]
    settings = MemorySettings(recent_rounds=x, min_summaries=y)
    sources = MemorySources.build(rounds, ranges)
    return WritingMaterials(
        character_name="角色", user_identity_name="身份", first_message="开场原文\r\n",
        character_definitions=[{"id": "d1", "order": 0, "content": "角色定义"}],
        user_definitions=[{"id": "d2", "order": 0, "content": "身份定义"}],
        **render_materials(plan_layout(sources, settings), sources, "身份").model_dump(),
        user_input=" 最新输入\r\n", state={"世界": {"日期": "第二天"}, "整数": 3, "布尔": True, "空": None},
    )


def response(text, name="game_content", finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"role": "model", "parts": [
        {"functionCall": {"name": name, "args": {"content": text}}}
    ]}}]}


def material_payload(value):
    return value.model_dump(exclude={"state_yaml"})


def test_runtime_preserves_json_and_detaches_mutations():
    value = materials()
    before = value.model_dump()
    source = SIMPLE.replace("return {api_type:", "m.state.changed = true; return {api_type:")
    built = PresetRuntime().build(source, value)
    assert built.api_type == "example"
    assert built.body["text"] == value.user_input
    assert built.body["state"]["整数"] == 3
    assert built.body["state"]["changed"] is True
    assert value.model_dump() == before
    original = {"text": " <custom>\r\n原文</custom>\n"}
    assert PresetRuntime().parse(SIMPLE, original).ai_output == original["text"]
    assert "changed" not in original


def test_fresh_context_for_every_entry_and_no_host_access():
    source = """
    let count = 0;
    function build(m) {count++; return {api_type:'test',body:{count}};}
    function parse(r) {return String(count) + ':' + [typeof fetch, typeof require,
        typeof process, typeof std, typeof os].join(',');}
    """
    runtime = PresetRuntime()
    assert runtime.build(source, materials()).body == {"count": 1}
    assert runtime.build(source, materials()).body == {"count": 1}
    assert runtime.parse(source, {}).ai_output == "0:undefined,undefined,undefined,undefined,undefined"


@pytest.mark.parametrize("source", [
    "function build( {", "function build(m) {return {};} ",
    SIMPLE + "\nthrow new Error('顶层失败');",
    SIMPLE.replace("return r.text;", "throw new Error('解析失败');"),
    SIMPLE.replace("return r.text;", "return Promise.resolve('异步');"),
    SIMPLE.replace("return r.text;", "return undefined;"),
    SIMPLE.replace("return r.text;", "return 42;"),
    SIMPLE.replace("return r.text;", "return '  \\n';"),
    SIMPLE.replace("return r.text;", "return {text:'错误类型'};"),
])
def test_execution_and_parse_contract_failures(source):
    with pytest.raises(PresetExecutionError) as error:
        PresetRuntime().parse(source, {"text": "ok"})
    assert error.value.stage == "parse"


@pytest.mark.parametrize("expression", [
    "null", "[]", "{api_type:' ',body:{}}", "{api_type:'x',body:[]}",
    "{api_type:'x',body:{},extra:1}", "{api_type:'x',body:{value:NaN}}",
    "{api_type:'x',body:{value:undefined}}", "{api_type:'x',body:{value:1n}}",
])
def test_build_contract_failures(expression):
    source = f"function build(m) {{return {expression};}} function parse(r){{return 'ok';}}"
    with pytest.raises(PresetExecutionError) as error:
        PresetRuntime().build(source, materials())
    assert error.value.stage == "build"


@pytest.mark.parametrize("location", ["top_level", "build", "parse"])
def test_time_limits(location):
    source = SIMPLE
    if location == "top_level":
        source += "\nwhile (true) {}"
    else:
        source = source.replace("return {api_type:" if location == "build" else "return r.text;",
                                "while(true) {} return {api_type:" if location == "build" else "while(true) {}")
    runtime = PresetRuntime(time_limit=0.02)
    with pytest.raises(PresetExecutionError):
        if location == "build":
            runtime.build(source, materials())
        else:
            runtime.parse(source, {})


def test_memory_stack_and_text_limits():
    runtime = PresetRuntime(memory_limit=2 * 1024 * 1024)
    source = SIMPLE.replace("return r.text;", "const a=[]; while(true){a.push(new Array(10000).fill('data'));}")
    with pytest.raises(PresetExecutionError):
        runtime.parse(source, {})
    with pytest.raises(PresetExecutionError):
        PresetRuntime().parse(SIMPLE.replace("return r.text;", "return parse(r);"), {})
    with pytest.raises(PresetExecutionError):
        PresetRuntime(max_text=100).parse(SIMPLE, {})
    with pytest.raises(PresetExecutionError):
        PresetRuntime(max_text=500).parse(SIMPLE, {"text": "a" * 1000})
    with pytest.raises(PresetExecutionError):
        PresetRuntime(max_text=500).parse(SIMPLE.replace("return r.text;", "return 'a'.repeat(1000);"), {})
    with pytest.raises(PresetExecutionError):
        PresetRuntime().parse(SIMPLE, {"text": float("nan")})


def test_unsafe_integers_do_not_silently_change_in_javascript():
    with pytest.raises(PresetExecutionError):
        PresetRuntime().parse(SIMPLE, {"text": "ok", "nested": {"values": [2**53 + 1]}})
    source = SIMPLE.replace("return {api_type:", "m.state.unsafe=2**53; return {api_type:")
    with pytest.raises(PresetExecutionError):
        PresetRuntime().build(source, materials())


@pytest.mark.parametrize("count,x,y,ranges,has_first", [
    (0, 5, 6, [], True), (3, 5, 6, [], True), (7, 5, 6, [], False),
    (20, 5, 6, [(1, 4), (5, 8), (9, 12)], False), (4, 0, 0, [(1, 4)], False),
])
def test_example_rearranges_turns_and_materials(count, x, y, ranges, has_first):
    value = materials(count, x, y, ranges)
    built = PresetRuntime().build(EXAMPLE, value)
    assert built.api_type == "google_generate_content"
    body = built.body
    contents = body["contents"]
    text = lambda item: item["parts"][0]["text"]
    all_text = "\n".join(text(item) for item in contents)
    assert (value.first_message in all_text) is has_first
    full = value.recent_rounds
    assert len(contents) == 6 + 2 * len(full)
    assert [item["role"] for item in contents] == ["model", "user"] * (3 + len(full))
    for i, item in enumerate(full):
        assert text(contents[2 + 2 * i]).endswith("<前缀>" + item.user_input + "<后缀>")
        assert text(contents[3 + 2 * i]) == "<填充>"
        assert text(contents[4 + 2 * i]).startswith(item.ai_output + "\n")
    assert text(contents[2 + 2 * len(full)]).endswith("<前缀>" + value.user_input + "<后缀>")
    if value.memory:
        assert text(contents[2]).count(f"<memory>\n{value.memory}\n</memory>") == 1
    assert value.state_yaml in text(contents[-2])
    assert yaml.safe_load(value.state_yaml) == value.state
    assert "角色定义\n身份定义" in body["systemInstruction"]["parts"][0]["text"]
    config = body["toolConfig"]["functionCallingConfig"]
    assert config["mode"] == "ANY" and config["allowedFunctionNames"] == ["game_content"]


def test_example_extracts_exact_closed_sections_without_executing_tools():
    text = "外部文字<report_nya~> 报告\r\n</report_nya~>\n忽略<content> 正文\r\n </content>尾文"
    original = response(text)
    before = deepcopy(original)
    parsed = PresetRuntime().parse(EXAMPLE, original)
    assert parsed.ai_output == "<report_nya~> 报告\r\n</report_nya~>\n<content> 正文\r\n </content>"
    assert original == before


@pytest.mark.parametrize("text", [
    "纯文本", "<report_nya~>报告</report_nya~><content>未闭合",
    "<report_nya~>报告</report_nya~></content><content>错误",
    "<report_nya~>报告</report_nya~><content>正文</content><content>重复</content>",
    "<report_nya~><content>嵌套</content></report_nya~>",
    "<report_nya~><content>交叉</report_nya~></content>",
    "<report_nya~> </report_nya~><content>正文</content>",
    "<report_nya~>报告</report_nya~><content> </content>",
])
def test_example_rejects_bad_tags(text):
    with pytest.raises(PresetExecutionError):
        PresetRuntime().parse(EXAMPLE, response(text))


@pytest.mark.parametrize("bad", [
    {}, {"candidates": []}, {"candidates": [{}, {}]},
    response("text", name="wrong_tool"), response("text", finish="MAX_TOKENS"),
    response(42),
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "无工具"}]}}]},
])
def test_example_rejects_invalid_provider_response(bad):
    with pytest.raises(PresetExecutionError):
        PresetRuntime().parse(EXAMPLE, bad)


@pytest.mark.parametrize("scope", ["source", "chat"])
def test_preset_api_scope_crud_and_transforms(database, chat, scope):
    root = "/api/writing-presets" if scope == "source" else f"/api/chats/{chat[0]}/writing-presets"
    other_root = f"/api/chats/{chat[0]}/writing-presets" if scope == "source" else "/api/writing-presets"
    async def scenario(client):
        assert (await client.get(root)).json() == []
        created = await client.post(root, json={"name": "预设", "source": SIMPLE})
        assert created.status_code == 201, created.text
        item = created.json()
        assert item["chat_id"] == (None if scope == "source" else chat[0])
        path = root + "/" + item["id"]
        assert (await client.get(path)).json() == item
        assert (await client.patch(path, json={})).json() == item
        assert (await client.patch(path, json={"name": "改名"})).json()["source"] == SIMPLE
        for bad in ({"name": " "}, {"source": None}, {"chat_id": chat[0]}, {"id": "指定ID"}):
            assert (await client.patch(path, json=bad)).status_code == 422
        other = (await client.post(other_root, json={"name": "其他", "source": SIMPLE})).json()
        foreign_path = root + "/" + other["id"]
        for method in ("GET", "PATCH", "DELETE"):
            result = await client.request(method, foreign_path, **({"json": {}} if method == "PATCH" else {}))
            assert result.status_code == 404
        for suffix, body in (("build", material_payload(materials())), ("parse", {"response": {"text": "ok"}})):
            assert (await client.post(foreign_path + "/" + suffix, json=body)).status_code == 404
        built = await client.post(path + "/build", json=material_payload(materials()))
        assert built.status_code == 200, built.text
        assert built.json()["body"]["text"] == " 最新输入\r\n"
        parsed = await client.post(path + "/parse", json={"response": {"text": " 原文\r\n"}})
        assert parsed.json() == {"ai_output": " 原文\r\n"}
        # Saving unfinished code is allowed; execution reports the failure separately.
        assert (await client.patch(path, json={"source": "unfinished("})).status_code == 200
        error = await client.post(path + "/parse", json={"response": {}})
        assert error.status_code == 422 and error.json()["detail"]["stage"] == "parse"
        assert (await client.get(path)).json()["source"] == "unfinished("
        assert (await client.delete(path)).status_code == 204
        assert (await client.get(path)).status_code == 404
        assert (await client.get("/api/chats/missing/writing-presets")).status_code == 404
    run_api(database, scenario)


def test_chat_preview_snapshot_and_archive_gate(database, chat):
    source = """
    function build(m) {return {api_type:'test',body:{materials:m}};}
    function parse(r) {return r.text;}
    """
    with database.transaction() as session:
        repo = Repository(session)
        preset = repo.add(WritingPreset(chat_id=chat[0], name="快照", source=source))
        repo.get(Chat, chat[0]).writing_preset_id = preset.id
        repo.opening_scene(chat[1]).first_message = "开场\r\n"
        definition = repo.add(Definition(character_id=chat[1], content="年龄{{ state['年龄'] }}", has_template=True))
        repo.add(Definition(character_id=chat[1], content="{{ missing }}", has_template=True, enabled=False))
        definition_id, preset_id = definition.id, preset.id
    async def scenario(client):
        path = f"/api/chats/{chat[0]}/writing-preview"
        first = await client.post(path, json={"user_input": "输入\r\n"})
        assert first.status_code == 200, first.text
        payload = first.json()
        assert payload["preset_id"] == preset_id and payload["state_snapshot_id"]
        value = payload["request"]["body"]["materials"]
        assert value["character_definitions"] == [{"id": definition_id, "order": 0, "content": "年龄16"}]
        assert value["memory"] == "" and value["recent_rounds"] == []
        assert value["first_message"] == "开场\r\n" and value["user_input"] == "输入\r\n"
        assert yaml.safe_load(value["state_yaml"]) == value["state"]
        # A copied preset is independently editable and cannot be deleted while selected.
        preset_path = f"/api/chats/{chat[0]}/writing-presets/{preset_id}"
        assert (await client.delete(preset_path)).status_code == 409
        with database.transaction() as session:
            archive = ArchiveRepository(session)
            current = archive.create_round(chat[0], "旧输入", "<content>旧输出</content>")
            archive.save_state(current.id, {"年龄": 17})
            archive.save_summary(current.id, "已保存摘要")
            round_id = current.id
        assert (await client.post(path, json={"user_input": "新输入"})).status_code == 409
        with database.transaction() as session:
            ArchiveRepository(session).save_decision(round_id)
        fresh = (await client.post(path, json={"user_input": "新输入"})).json()
        assert fresh["state_snapshot_id"] != payload["state_snapshot_id"]
        value = fresh["request"]["body"]["materials"]
        assert value["character_definitions"][0]["content"] == "年龄17"
        assert value["recent_rounds"][0]["ai_output"] == "<content>旧输出</content>"
        # Template failure precedes build failure, and neither writes database results.
        definition_path = f"/api/chats/{chat[0]}/character/definitions/{definition_id}"
        await client.patch(definition_path, json={"content": "{{ missing }}"})
        await client.patch(preset_path, json={"source": "broken("})
        failure = await client.post(path, json={"user_input": "新输入"})
        assert failure.status_code == 422 and failure.json()["detail"]["definition_id"] == definition_id
        await client.patch(definition_path, json={"enabled": False})
        assert (await client.post(path, json={"user_input": "新输入"})).json()["detail"]["stage"] == "build"
        await client.patch(f"/api/chats/{chat[0]}", json={"writing_preset_id": None})
        assert (await client.post(path, json={"user_input": "输入"})).status_code == 409
        assert (await client.delete(preset_path)).status_code == 204
        assert (await client.post("/api/chats/missing/writing-preview", json={"user_input": "输入"})).status_code == 404
    run_api(database, scenario)
    with database.read() as session:
        repo = Repository(session)
        assert len(repo.rounds(chat[0])) == 1
        assert repo.rounds(chat[0])[0].archive_step == "complete"
        assert repo.get(Definition, definition_id).content == "{{ missing }}"


def test_preset_creation_copy_and_source_deletion_independence(database):
    async def scenario(client):
        source = (await client.post("/api/writing-presets", json={"name": "来源", "source": SIMPLE})).json()
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        payload = {"title": "聊天", "character_id": character["id"], "user_identity_id": identity["id"],
                   "writing_preset_id": source["id"]}
        first = (await client.post("/api/chats", json=payload)).json()
        second = (await client.post("/api/chats", json=payload)).json()
        first_path = f"/api/chats/{first['id']}/writing-presets/{first['writing_preset_id']}"
        second_path = f"/api/chats/{second['id']}/writing-presets/{second['writing_preset_id']}"
        assert first["writing_preset_id"] != second["writing_preset_id"] != source["id"]
        assert (await client.patch(first_path, json={"source": "unfinished("})).status_code == 200
        assert (await client.get(second_path)).json()["source"] == SIMPLE
        # Source scope cannot be overridden through a query argument.
        assert (await client.get(f"/api/writing-presets/{first['writing_preset_id']}?chat_id={first['id']}")).status_code == 404
        foreign = f"/api/chats/{second['id']}/writing-presets/{first['writing_preset_id']}"
        assert (await client.get(foreign)).status_code == 404
        assert (await client.delete("/api/writing-presets/" + source["id"])).status_code == 204
        assert (await client.get(second_path)).json()["source"] == SIMPLE
        assert (await client.post(f"/api/chats/{second['id']}/writing-preview", json={"user_input": "输入"})).status_code == 200
        docs = (await client.get("/openapi.json")).json()
        endpoint = docs["paths"]["/api/chats/{chat_id}/writing-presets/{preset_id}/build"]["post"]
        assert {p["name"] for p in endpoint["parameters"] if p["in"] == "path"} == {"chat_id", "preset_id"}
    run_api(database, scenario)
