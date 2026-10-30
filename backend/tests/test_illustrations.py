import asyncio
from concurrent.futures import Future
import json

import httpx
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.modules.illustrations.comfyui import ComfyUIClient
from backend.modules.illustrations.workflow import fill_workflow, prompt_fields, validate_workflow
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Illustration, ModelConfig
from backend.repository.queries import Repository
from backend.shared.errors import IllustrationError
from backend.tests.state_fixtures import STATE_SCHEMA, WORLD
from backend.tests.test_writing import database_contents
from backend.workflows.illustration import auto_illustration

PNG = b"\x89PNG\r\n\x1a\nfake-image"
WORKFLOW = {
    "3": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", "steps": 20}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{ width }}", "height": "{{height}}"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece, {{prompt}}"}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative_prompt}}"}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0]}},
}
FIELDS = {"prompt": "1girl, school gate, sunset", "negative_prompt": "lowres"}


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
                        image_directory=str(tmp_path / "images"), comfyui_poll_seconds=0)
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
        "instructions": "使用英文 danbooru 标签。{{char}} 是黑长发少女。", **extra})
    assert created.status_code == 201, created.text
    workflow = created.json()
    patched = await client.patch(f"/api/chats/{chat_id}", json={"illustration": {
        "mode": mode, "image_workflow_id": workflow["id"], "model_config_id": model_id}})
    assert patched.status_code == 200, patched.text
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
        assert detail["illustration"]["mode"] == "manual" and detail["image_workflows"][0]["id"] == workflow["id"]

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
        assert "使用英文 danbooru 标签。角色 是黑长发少女。" in prompt
        assert '"negative_prompt"、"prompt"' in prompt and "她坐在车后座上。" in prompt and "<think>" not in prompt
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
        assert preview.json() == {"image_workflow_id": workflow["id"], "fields": FIELDS}
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


def test_chat_creation_copies_selected_workflow_and_prompt_model(database, tmp_path):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        model = (await client.post("/api/model-configs", json={
            "name": "提示词", "api_type": "google_generate_content", "base_url": "https://provider.test/v1beta",
            "model": "m"})).json()
        workflow = (await client.post("/api/image-workflows", json={
            "name": "SDXL", "base_url": "http://127.0.0.1:8188", "workflow": WORKFLOW, "width": 832, "height": 1216})).json()
        created = await client.post("/api/chats", json={
            "title": "新聊天", "character_id": character["id"], "user_identity_id": identity["id"],
            "illustration": {"mode": "scene_change", "image_workflow_id": workflow["id"], "model_config_id": model["id"]}})
        assert created.status_code == 201, created.text
        detail = created.json()
        [copy] = detail["image_workflows"]
        assert copy["id"] != workflow["id"] and copy["chat_id"] == detail["id"] and copy["height"] == 1216
        [model_copy] = detail["model_configs"]
        assert detail["illustration"] == {"mode": "scene_change", "image_workflow_id": copy["id"],
                                          "model_config_id": model_copy["id"]}
        plain = (await client.post("/api/chats", json={
            "title": "无插图", "character_id": character["id"], "user_identity_id": identity["id"]})).json()
        assert plain["illustration"] == {"mode": "off", "image_workflow_id": None, "model_config_id": None}
        assert plain["image_workflows"] == []
    run(database, tmp_path, scenario)
