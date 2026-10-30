import asyncio
from concurrent.futures import Future
import json

import httpx
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.illustrations.comfyui import ComfyUIClient
from backend.illustrations.errors import IllustrationError
from backend.illustrations.jobs import auto_illustration
from backend.illustrations.models import Illustration
from backend.illustrations.placeholders import fill_workflow, image_inputs, prompt_fields, validate_workflow
from backend.illustrations.templates import IMAGE_TO_IMAGE, TEXT_TO_IMAGE
from backend.repository.archive import ArchiveRepository
from backend.repository.models import ModelConfig
from backend.repository.queries import Repository
from backend.tests.state_fixtures import STATE_SCHEMA, WORLD
from backend.tests.test_writing import database_contents

PNG = b"\x89PNG\r\n\x1a\nfake-image"
WORKFLOW = {
    "3": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", "steps": 20}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{ width }}", "height": "{{height}}"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece, {{prompt}}"}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative_prompt}}"}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0]}},
}
FIELDS = {"prompt": "1girl, school gate, sunset", "negative_prompt": "lowres"}
TEMPLATE = """使用英文标签。{{ char }} 与 {{ user }}。
{% for p in focus %}主角：{{ p.name }}（{{ p.appearance }}）
{% endfor %}{% for p in others %}其他：{{ p.name }}
{% endfor %}地点：{{ state["世界"]["地点"] }}
正文：{{ round.content }}"""


class InlineExecutor:
    def submit(self, function, *args):
        future = Future()
        future.set_result(function(*args))
        return future

    def shutdown(self, **_):
        pass


def llm_handler(calls, fields=FIELDS):
    def handler(request):
        calls.append(json.loads(request.content))
        text = json.dumps(fields, ensure_ascii=False)
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]})
    return handler


def comfy_handler(calls, *, reject=False, history_error=False):
    polls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "127.0.0.1" and request.url.port == 8188
        if request.method == "POST" and request.url.path == "/prompt":
            if reject:
                return httpx.Response(400, json={"error": {"message": "Prompt outputs failed validation"},
                                                 "node_errors": {"6": {"class_type": "CLIPTextEncode",
                                                                       "errors": [{"message": "Required input is missing",
                                                                                   "details": "clip"}]}}})
            return httpx.Response(200, json={"prompt_id": "job-1", "number": 1, "node_errors": {}})
        if request.url.path == "/history/job-1":
            polls.append(1)
            if len(polls) == 1:
                return httpx.Response(200, json={})
            if history_error:
                return httpx.Response(200, json={"job-1": {"outputs": {}, "status": {"status_str": "error", "messages": [
                    ["execution_error", {"node_type": "KSampler", "exception_message": "CUDA out of memory"}]]}}})
            return httpx.Response(200, json={"job-1": {"status": {"status_str": "success", "completed": True},
                                                       "outputs": {"9": {"images": [
                                                           {"filename": "preview.png", "subfolder": "", "type": "temp"},
                                                           {"filename": "out_0001.png", "subfolder": "lore", "type": "output"},
                                                       ]}}}})
        if request.url.path == "/view":
            assert dict(request.url.params) == {"filename": "out_0001.png", "subfolder": "lore", "type": "output"}
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        return httpx.Response(404)
    return handler


def run(database, tmp_path, scenario, *, llm=None, comfy=None):
    settings = Settings(database_url=database.engine.url.render_as_string(hide_password=False),
                        image_directory=str(tmp_path / "images"), media_directory=str(tmp_path / "media"),
                        comfyui_poll_seconds=0)
    app = create_app(settings, llm_transport=httpx.MockTransport(llm or (lambda r: httpx.Response(500))),
                     comfyui_transport=httpx.MockTransport(comfy or (lambda r: httpx.Response(500))),
                     illustration_executor=InlineExecutor())

    async def main():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                await scenario(client)
    asyncio.run(main())


def archived_round(database, chat_id, place="校门外", date="2026-10-19", no=None):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        record = repo.create_round(chat_id, "我问她为什么这么晚", "<think>略</think><content>她坐在车后座上。</content>")
        repo.save_state(record.id, {"世界": {**WORLD, "地点": place, "日期": date}, "年龄": 16})
        repo.save_summary(record.id, "2026-10-19—17:53—校门外\n她解释被老师留下。")
        repo.save_decision(record.id)
        return record.id


@pytest.fixture
def illustrated_chat(database, chat):
    with database.transaction() as session:
        model = Repository(session).add(ModelConfig(chat_id=chat[0], name="提示词模型", api_type="google_generate_content",
                                                    base_url="https://provider.test/v1beta", api_key="k", model="m"))
    return {"chat_id": chat[0], "model_id": model.id}


async def setup_workflow(client, chat_id, model_id, mode="manual", **extra):
    created = await client.post(f"/api/chats/{chat_id}/image-workflows", json={
        "name": "SDXL", "base_url": "http://127.0.0.1:8188", "workflow": WORKFLOW,
        "prompt_template": TEMPLATE, **extra})
    assert created.status_code == 201, created.text
    workflow = created.json()
    settings = await client.put(f"/api/chats/{chat_id}/illustration-settings", json={
        "mode": mode, "image_workflow_id": workflow["id"], "model_config_id": model_id})
    assert settings.status_code == 200, settings.text
    return workflow


def test_workflow_placeholders():
    assert prompt_fields(WORKFLOW) == ["negative_prompt", "prompt"]
    filled = fill_workflow(WORKFLOW, {**FIELDS, "seed": 42, "width": 1344, "height": 768})
    assert filled["3"]["inputs"]["seed"] == 42 and filled["5"]["inputs"]["width"] == 1344
    assert filled["6"]["inputs"]["text"] == "masterpiece, 1girl, school gate, sunset"
    assert WORKFLOW["3"]["inputs"]["seed"] == "{{seed}}"
    for invalid in ({}, {"1": {"inputs": {}}}, {"1": {"class_type": "SaveImage", "inputs": {"seed": "{{seed}}"}}}):
        with pytest.raises(IllustrationError):
            validate_workflow(invalid)
    with pytest.raises(IllustrationError):
        fill_workflow(WORKFLOW, {"seed": 1, "width": 1, "height": 1})


def test_generation_queues_renders_and_serves_the_image(database, illustrated_chat, tmp_path):
    ids, llm_calls, comfy_calls = illustrated_chat, [], []
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        workflow = await setup_workflow(client, ids["chat_id"], ids["model_id"])
        assert workflow["prompt_fields"] == ["negative_prompt", "prompt"]
        detail = (await client.get(f"/api/chats/{ids['chat_id']}")).json()
        assert "illustration" not in detail and "image_workflows" not in detail  # The core doesn't know the feature.

        queued = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations")
        assert queued.status_code == 202, queued.text
        assert queued.json()["status"] == "pending" and queued.json()["width"] == 1344
        [record] = (await client.get(f"/api/chats/{ids['chat_id']}/illustrations")).json()
        assert record["status"] == "ready", record
        assert record["prompt"] == FIELDS and record["media_type"] == "image/png"
        image = await client.get(f"/api/chats/{ids['chat_id']}/illustrations/{record['id']}/image")
        assert image.status_code == 200 and image.content == PNG
        assert "immutable" in image.headers["cache-control"]

        hidden = await client.patch(f"/api/chats/{ids['chat_id']}/illustrations/{record['id']}", json={"hidden": True})
        assert hidden.json()["hidden"] is True
        assert (await client.delete(f"/api/chats/{ids['chat_id']}/image-workflows/{workflow['id']}")).status_code == 409
        assert (await client.delete(f"/api/chats/{ids['chat_id']}/model-configs/{ids['model_id']}")).status_code == 409

        queued_body = json.loads(comfy_calls[0].content)
        assert queued_body["prompt"]["3"]["inputs"]["seed"] == record["seed"]
        assert queued_body["prompt"]["7"]["inputs"]["text"] == "lowres"
        prompt = llm_calls[0]["contents"][0]["parts"][0]["text"]
        assert "使用英文标签。角色 与 身份。" in prompt and "主角：角色（）" in prompt and "其他：身份" in prompt
        assert "地点：校门外" in prompt and "她坐在车后座上。" in prompt and "<think>" not in prompt
        assert '恰好包含这些字符串字段："negative_prompt"、"prompt"' in prompt
        assert llm_calls[0]["generationConfig"]["responseMimeType"] == "application/json"

        assert (await client.delete(f"/api/chats/{ids['chat_id']}")).status_code == 204
        assert not (tmp_path / "images" / ids["chat_id"]).exists()
    run(database, tmp_path, scenario, llm=llm_handler(llm_calls), comfy=comfy_handler(comfy_calls))
    assert (tmp_path / "images").exists()


@pytest.mark.parametrize("options, message", [
    ({"reject": True}, "ComfyUI 拒绝了工作流：Prompt outputs failed validation；节点 6（CLIPTextEncode）：Required input is missing clip"),
    ({"history_error": True}, "ComfyUI 执行失败：节点 KSampler：CUDA out of memory"),
])
def test_failures_are_recorded_and_retry_adds_an_attempt(database, illustrated_chat, tmp_path, options, message):
    ids = illustrated_chat
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        await setup_workflow(client, ids["chat_id"], ids["model_id"])
        url = f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations"
        assert (await client.post(url)).status_code == 202
        assert (await client.post(url)).status_code == 202
        records = (await client.get(f"/api/chats/{ids['chat_id']}/illustrations")).json()
        assert [r["status"] for r in records] == ["failed", "failed"]
        assert records[0]["error"] == message and records[0]["prompt"] == FIELDS
        assert (await client.get(f"/api/chats/{ids['chat_id']}/illustrations/{records[0]['id']}/image")).status_code == 404
    run(database, tmp_path, scenario, llm=llm_handler([]), comfy=comfy_handler([], **options))


def test_invalid_model_output_fails_before_comfyui(database, illustrated_chat, tmp_path):
    ids, comfy_calls = illustrated_chat, []
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        await setup_workflow(client, ids["chat_id"], ids["model_id"])
        await client.post(f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations")
        [record] = (await client.get(f"/api/chats/{ids['chat_id']}/illustrations")).json()
        assert record["status"] == "failed" and record["error"] == "插图提示词响应缺少字符串字段：negative_prompt"
    run(database, tmp_path, scenario, llm=llm_handler([], {"prompt": "only"}), comfy=comfy_handler(comfy_calls))
    assert comfy_calls == []


def test_prompt_preview_and_preconditions_change_nothing(database, illustrated_chat, tmp_path):
    ids = illustrated_chat
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        url = f"/api/chats/{ids['chat_id']}/rounds/{round_id}"
        assert (await client.post(url + "/illustrations")).json()["detail"] == "聊天未开启插图"
        workflow = await setup_workflow(client, ids["chat_id"], ids["model_id"])
        before = database_contents(database)
        preview = await client.post(url + "/illustration-prompt")
        assert preview.status_code == 200, preview.text
        assert preview.json() == {"image_workflow_id": workflow["id"], "focus": ["角色"], "fields": FIELDS}
        assert database_contents(database) == before
        bad = await client.post(f"/api/chats/{ids['chat_id']}/image-workflows", json={
            "name": "坏", "base_url": "http://127.0.0.1:8188", "workflow": {"1": {"class_type": "SaveImage", "inputs": {}}}})
        assert bad.status_code == 422
    run(database, tmp_path, scenario, llm=llm_handler([]))


def test_auto_modes_after_archive(database, illustrated_chat, tmp_path):
    ids = illustrated_chat

    async def scenario(client):
        await setup_workflow(client, ids["chat_id"], ids["model_id"], mode="scene_change")
        first = archived_round(database, ids["chat_id"], place="教室")
        second = archived_round(database, ids["chat_id"], place="教室")
        third = archived_round(database, ids["chat_id"], place="校门外")
        # No illustration yet: the first archived round gets one even without a scene change.
        assert auto_illustration(database, ids["chat_id"], second) is not None
        with database.transaction() as session:
            session.query(Illustration).update({"status": "failed", "error": "x"})
        assert auto_illustration(database, ids["chat_id"], second) is None
        assert auto_illustration(database, ids["chat_id"], third) is not None
        # The first round compares with the initial state, whose place is empty.
        assert auto_illustration(database, ids["chat_id"], first) is not None
    run(database, tmp_path, scenario)


def test_unfinished_jobs_are_interrupted_on_startup(database, illustrated_chat, tmp_path):
    round_id = archived_round(database, illustrated_chat["chat_id"])
    with database.transaction() as session:
        Repository(session).add(Illustration(chat_id=illustrated_chat["chat_id"], round_id=round_id,
                                             status="rendering", seed=1, width=64, height=64))

    async def scenario(client):
        [record] = (await client.get(f"/api/chats/{illustrated_chat['chat_id']}/illustrations")).json()
        assert record["status"] == "failed" and record["error"] == "服务重启，任务已中断"
    run(database, tmp_path, scenario)


def test_comfyui_timeout_and_bad_output():
    clock = iter(range(100))
    client = ComfyUIClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, json={"prompt_id": "p"} if r.url.path == "/prompt" else {})),
        timeout_seconds=3, sleep=lambda _: None, clock=lambda: next(clock))
    with pytest.raises(IllustrationError, match="生成超时"):
        client.render("http://127.0.0.1:8188", WORKFLOW)

    def wrong_type(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "p"})
        if request.url.path == "/history/p":
            return httpx.Response(200, json={"p": {"outputs": {"9": {"images": [{"filename": "a.gif"}]}}}})
        return httpx.Response(200, content=b"GIF", headers={"content-type": "image/gif"})
    with pytest.raises(IllustrationError, match="不是 PNG"):
        ComfyUIClient(transport=httpx.MockTransport(wrong_type)).render("http://127.0.0.1:8188", WORKFLOW)

    def unreachable(request):
        raise httpx.ConnectError("refused")
    with pytest.raises(IllustrationError, match="无法连接 ComfyUI"):
        ComfyUIClient(transport=httpx.MockTransport(unreachable)).render("http://127.0.0.1:8188", WORKFLOW)


def test_chat_setup_import_and_cast_copy(database, tmp_path):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "ABC 学园", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        model = (await client.post("/api/model-configs", json={
            "name": "提示词", "api_type": "google_generate_content", "base_url": "https://provider.test/v1beta",
            "model": "m"})).json()
        workflow = (await client.post("/api/image-workflows", json={
            "name": "SDXL", "base_url": "http://127.0.0.1:8188", "workflow": WORKFLOW, "width": 832, "height": 1216})).json()
        assert workflow["prompt_template"] == TEXT_TO_IMAGE and workflow["image_inputs"] == []
        cast = await client.put(f"/api/characters/{character['id']}/cast", json={"members": [
            {"name": "小明", "appearance": "short hair"}, {"name": "小红", "appearance": "long hair"}]})
        assert cast.status_code == 200, cast.text
        kept = cast.json()[1]
        again = await client.put(f"/api/characters/{character['id']}/cast", json={"members": [
            {**kept, "appearance": "long black hair"}]})
        assert again.json() == [{**kept, "appearance": "long black hair"}]  # An edit keeps the id.
        assert (await client.put(f"/api/user-identities/{identity['id']}/appearance", json={"appearance": "眼镜"})).status_code == 200

        created = (await client.post("/api/chats", json={
            "title": "新聊天", "character_id": character["id"], "user_identity_id": identity["id"],
            "model_bindings": {"writing": model["id"]}})).json()
        chat = f"/api/chats/{created['id']}"
        assert (await client.get(chat + "/illustration-settings")).json()["mode"] == "off"
        [member] = (await client.get(chat + "/cast")).json()
        assert member["name"] == "小红" and member["id"] != kept["id"]
        assert (await client.get(chat + "/appearance")).json()["appearance"] == "眼镜"
        options = (await client.get(chat + "/focus-options")).json()
        assert [o["name"] for o in options["options"]] == ["小红", "身份"] and options["default"] == [member["id"]]

        settings = await client.post(chat + "/illustration-setup", json={
            "mode": "scene_change", "image_workflow_id": workflow["id"], "model_config_id": model["id"]})
        assert settings.status_code == 200, settings.text
        [copy] = (await client.get(chat + "/image-workflows")).json()
        assert copy["id"] != workflow["id"] and copy["height"] == 1216
        # The binding's copy of the same model config is reused, not duplicated.
        assert settings.json() == {"mode": "scene_change", "image_workflow_id": copy["id"], "focus": [],
                                   "model_config_id": created["model_bindings"]["writing"]}
        assert len((await client.get(chat + "/model-configs")).json()) == 1
        assert (await client.post(chat + "/image-workflows/import", json={"source_id": workflow["id"]})).status_code == 201
        assert len((await client.get(chat + "/image-workflows")).json()) == 2
        defaults = (await client.get("/api/image-workflows/default-templates")).json()
        assert defaults == {"text_to_image": TEXT_TO_IMAGE, "image_to_image": IMAGE_TO_IMAGE}
    run(database, tmp_path, scenario)


def test_focus_defaults_overrides_and_soft_limit(database, illustrated_chat, tmp_path):
    ids, llm_calls = illustrated_chat, []
    round_id = archived_round(database, ids["chat_id"])

    def prompt_of(call):
        return call["contents"][0]["parts"][0]["text"]

    async def scenario(client):
        chat = f"/api/chats/{ids['chat_id']}"
        workflow = await setup_workflow(client, ids["chat_id"], ids["model_id"])
        # No cast: the character card itself is the default.
        assert (await client.post(f"{chat}/rounds/{round_id}/illustration-prompt")).json()["focus"] == ["角色"]
        members = (await client.put(chat + "/cast", json={"members": [
            {"name": "甲", "appearance": "tall"}, {"name": "乙", "appearance": "short"}, {"name": "丙"}]})).json()
        # With a cast: its first member, and the card's name is no longer offered.
        assert (await client.post(f"{chat}/rounds/{round_id}/illustration-prompt")).json()["focus"] == ["甲"]
        assert "主角：甲（tall）" in prompt_of(llm_calls[-1]) and "其他：乙" in prompt_of(llm_calls[-1]) and "其他：身份" in prompt_of(llm_calls[-1])
        # The chat's manual choice overrides the default; a removed id is dropped.
        await client.put(chat + "/illustration-settings", json={
            "mode": "manual", "image_workflow_id": workflow["id"], "model_config_id": ids["model_id"],
            "focus": [members[1]["id"], "user", "gone"]})
        assert (await client.post(f"{chat}/rounds/{round_id}/illustration-prompt")).json()["focus"] == ["乙", "身份"]
        # One attempt can override again, and more than two is allowed.
        everyone = [m["id"] for m in members] + ["user"]
        queued = await client.post(f"{chat}/rounds/{round_id}/illustrations", json={"focus": everyone})
        assert [p["name"] for p in queued.json()["focus"]] == ["甲", "乙", "丙", "身份"]
    run(database, tmp_path, scenario, llm=llm_handler(llm_calls), comfy=comfy_handler([]))


I2I_WORKFLOW = {**WORKFLOW, "10": {"class_type": "LoadImage", "inputs": {"image": "{{image:focus_1}}"}}}


def test_image_to_image_uploads_the_reference_and_requires_one(database, illustrated_chat, tmp_path):
    ids, llm_calls, comfy_calls = illustrated_chat, [], []
    round_id = archived_round(database, ids["chat_id"])
    plain = comfy_handler(comfy_calls)

    def comfy(request):
        if request.url.path == "/upload/image":
            comfy_calls.append(request)
            assert b'name="overwrite"' in request.content and PNG in request.content
            return httpx.Response(200, json={"name": "ref.png", "subfolder": "lore", "type": "input"})
        return plain(request)

    async def scenario(client):
        chat = f"/api/chats/{ids['chat_id']}"
        assert (await client.post("/api/media", content=b"not an image")).status_code == 415
        uploaded = await client.post("/api/media", content=PNG)
        assert uploaded.status_code == 201, uploaded.text
        name = uploaded.json()["name"]
        served = await client.get(uploaded.json()["url"])
        assert served.content == PNG and served.headers["content-type"] == "image/png"
        assert (await client.get("/api/media/..%2Fsecret.png")).status_code == 404

        workflow = await setup_workflow(client, ids["chat_id"], ids["model_id"], workflow=I2I_WORKFLOW)
        assert workflow["image_inputs"] == ["image:focus_1"]
        await client.put(chat + "/cast", json={"members": [{"name": "甲"}]})
        url = f"{chat}/rounds/{round_id}/illustrations"

        # No reference image: an error on the attempt, and no model call or render is spent.
        await client.post(url)
        [failed] = (await client.get(chat + "/illustrations")).json()
        assert failed["status"] == "failed" and failed["error"] == "甲 没有参考图，请先上传参考图"
        assert llm_calls == [] and comfy_calls == []

        members = (await client.get(chat + "/cast")).json()
        assert (await client.put(chat + "/cast", json={"members": [{**members[0], "reference_image": "../x.png"}]})).status_code == 422
        await client.put(chat + "/cast", json={"members": [{**members[0], "reference_image": name}]})
        await client.post(url)
        record = (await client.get(chat + "/illustrations")).json()[-1]
        assert record["status"] == "ready", record
        queued = json.loads(next(c for c in comfy_calls if c.url.path == "/prompt").content)
        assert queued["prompt"]["10"]["inputs"]["image"] == "lore/ref.png"

        # A second required image without a second main character is also an error.
        doubled = {**I2I_WORKFLOW, "11": {"class_type": "LoadImage", "inputs": {"image": "{{image:focus_2}}"}}}
        await client.patch(f"{chat}/image-workflows/{workflow['id']}", json={"workflow": doubled})
        await client.post(url)
        record = (await client.get(chat + "/illustrations")).json()[-1]
        assert record["error"] == "工作流需要第 2 位主要人物的参考图，但本次只有 1 位主要人物"
        bad = {**WORKFLOW, "10": {"class_type": "LoadImage", "inputs": {"image": "{{image:other}}"}}}
        assert (await client.patch(f"{chat}/image-workflows/{workflow['id']}", json={"workflow": bad})).status_code == 422
    run(database, tmp_path, scenario, llm=llm_handler(llm_calls), comfy=comfy)


def test_templates_are_validated_and_render_errors_fail_the_attempt(database, illustrated_chat, tmp_path):
    ids, comfy_calls = illustrated_chat, []
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        chat = f"/api/chats/{ids['chat_id']}"
        workflow = await setup_workflow(client, ids["chat_id"], ids["model_id"])
        broken = await client.patch(f"{chat}/image-workflows/{workflow['id']}", json={"prompt_template": "{% for %}"})
        assert broken.status_code == 422
        unknown = await client.patch(f"{chat}/image-workflows/{workflow['id']}", json={"prompt_template": "{{ nope }}"})
        assert unknown.status_code == 200
        await client.post(f"{chat}/rounds/{round_id}/illustrations")
        [record] = (await client.get(chat + "/illustrations")).json()
        assert record["status"] == "failed" and "提示词模板错误" in record["error"] and "nope" in record["error"]
    run(database, tmp_path, scenario, llm=llm_handler([]), comfy=comfy_handler(comfy_calls))
    assert comfy_calls == []


def test_image_inputs_are_in_main_character_order():
    assert image_inputs(I2I_WORKFLOW) == ["image:focus_1"]
    many = {"1": {"class_type": "A", "inputs": {"a": "{{image:focus_10}}", "b": "{{image:focus_2}}", "c": "{{prompt}}"}}}
    assert image_inputs(many) == ["image:focus_2", "image:focus_10"] and prompt_fields(many) == ["prompt"]
