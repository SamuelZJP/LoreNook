import asyncio
from concurrent.futures import Future
import json

import httpx
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.illustrations.comfyui import ComfyUIClient, RenderProgress
from backend.illustrations.errors import IllustrationError
from backend.illustrations.jobs import auto_illustration
from backend.illustrations.models import Illustration, ImageWorkflow
from backend.illustrations.placeholders import fill_workflow, uses_images, validate_workflow
from backend.illustrations.progress import ProgressBoard, progress_events
from backend.illustrations.prompt import MAX_IMAGES, reference_images, render_prompt
from backend.illustrations.schemas import IllustrationContext, IllustrationProgress, Subject
from backend.repository.archive import ArchiveRepository
from backend.repository.queries import Repository
from backend.tests.state_fixtures import STATE_SCHEMA, WORLD
from backend.tests.test_writing import database_contents

PNG = b"\x89PNG\r\n\x1a\nfake-image"
WORKFLOW = {
    "3": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", "steps": 20}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{ width }}", "height": "{{height}}"}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece, {{prompt}}"}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0]}},
}
IMAGES_WORKFLOW = {**WORKFLOW, "10": {"class_type": "LLMAPIProNode", "inputs": {"images": "{{images}}"}}}


class InlineExecutor:
    def submit(self, function, *args):
        future = Future()
        future.set_result(function(*args))
        return future

    def shutdown(self, **_):
        pass


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


def no_model_call(request):
    pytest.fail("Illustrations must not call a model")


def run(database, tmp_path, scenario, *, comfy=None):
    settings = Settings(database_url=database.engine.url.render_as_string(hide_password=False),
                        image_directory=str(tmp_path / "images"), media_directory=str(tmp_path / "media"),
                        comfyui_poll_seconds=0)
    app = create_app(settings, llm_transport=httpx.MockTransport(no_model_call),
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
def illustrated_chat(chat):
    return {"chat_id": chat[0]}


async def setup_workflow(client, chat_id, mode="manual", **extra):
    created = await client.post(f"/api/chats/{chat_id}/image-workflows", json={
        "name": "SDXL", "base_url": "http://127.0.0.1:8188", "workflow": WORKFLOW, **extra})
    assert created.status_code == 201, created.text
    workflow = created.json()
    settings = await client.put(f"/api/chats/{chat_id}/illustration-settings", json={
        "mode": mode, "image_workflow_id": workflow["id"]})
    assert settings.status_code == 200, settings.text
    return workflow


def test_workflow_placeholders():
    filled = fill_workflow(IMAGES_WORKFLOW, {"prompt": "正文", "images": '["a.png"]', "seed": 42, "width": 1344, "height": 768})
    assert filled["3"]["inputs"]["seed"] == 42 and filled["5"]["inputs"]["width"] == 1344
    assert filled["6"]["inputs"]["text"] == "masterpiece, 正文"
    assert filled["10"]["inputs"]["images"] == '["a.png"]'  # A real array would be read as a node link.
    assert WORKFLOW["3"]["inputs"]["seed"] == "{{seed}}"
    assert uses_images(IMAGES_WORKFLOW) and not uses_images(WORKFLOW)
    assert validate_workflow(IMAGES_WORKFLOW) == IMAGES_WORKFLOW
    for invalid in ({}, {"1": {"inputs": {}}}, {"1": {"class_type": "SaveImage", "inputs": {"seed": "{{seed}}"}}}):
        with pytest.raises(IllustrationError):
            validate_workflow(invalid)
    for name in ("negative_prompt", "image:focus_1"):
        unknown = {**WORKFLOW, "7": {"class_type": "A", "inputs": {"text": f"{{{{{name}}}}}"}}}
        with pytest.raises(IllustrationError, match="不支持的占位符"):
            validate_workflow(unknown)
    with pytest.raises(IllustrationError):
        fill_workflow(WORKFLOW, {"seed": 1, "width": 1, "height": 1})


def context(**values):
    return IllustrationContext(**{
        "user_input": "我问她为什么这么晚", "ai_output": "<think>略</think><content>她坐在车后座上。</content>",
        "state": {"世界": {"地点": "校门外"}, "年龄": 16}, "focus": [Subject(id="a", name="小红")], "others": [],
        "image_workflow_id": "w", "base_url": "http://127.0.0.1:8188", "workflow": WORKFLOW, "width": 64, "height": 64,
        **values})


def test_prompt_is_the_agreed_format():
    focus = [Subject(id="a", name="小红", appearance=" 长发 ", reference_image="red.png"),
             Subject(id="b", name="小明", reference_image="ming.png")]
    others = [Subject(id="c", name="老师", appearance="戴眼镜"), Subject(id="d", name="路人")]
    assert render_prompt(context(focus=focus, others=others), ["red.png", "ming.png"]) == """## 用户输入
我问她为什么这么晚

## 剧情内容
她坐在车后座上。

## 状态信息
世界:
  地点: 校门外
年龄: 16

## 人物外貌
<小红>
参考图：图 1
长发
</小红>
<小明>
参考图：图 2
</小明>
<老师>
戴眼镜
</老师>

## 中心人物
小红、小明

请按系统说明从以上上下文选定画面瞬间，直接输出提示词正文。"""


def test_prompt_without_descriptions_or_sent_images():
    person = Subject(id="a", name="小红", reference_image="red.png")
    prompt = render_prompt(context(focus=[person]), [])  # The workflow takes no images, so none are numbered.
    assert "## 人物外貌\n（无）\n" in prompt and "参考图" not in prompt and "## 中心人物\n小红\n" in prompt


def test_reference_images_keep_order_share_numbers_and_stop_at_the_limit():
    people = [Subject(id=str(n), name=str(n), reference_image=f"{n}.png") for n in range(MAX_IMAGES + 2)]
    assert reference_images(people) == [f"{n}.png" for n in range(MAX_IMAGES)]
    shared = [Subject(id="a", name="甲", reference_image="same.png"), Subject(id="b", name="乙"),
              Subject(id="c", name="丙", reference_image="same.png"), Subject(id="d", name="丁", reference_image="d.png")]
    images = reference_images(shared)
    assert images == ["same.png", "d.png"]
    prompt = render_prompt(context(focus=shared), images)
    assert "<丙>\n参考图：图 1\n</丙>" in prompt and "<丁>\n参考图：图 2\n</丁>" in prompt and "<乙>" not in prompt


def test_generation_queues_renders_and_serves_the_image(database, illustrated_chat, tmp_path):
    ids, comfy_calls = illustrated_chat, []
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        workflow = await setup_workflow(client, ids["chat_id"])
        detail = (await client.get(f"/api/chats/{ids['chat_id']}")).json()
        assert "illustration" not in detail and "image_workflows" not in detail  # The core doesn't know the feature.

        queued = await client.post(f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations")
        assert queued.status_code == 202, queued.text
        assert queued.json()["status"] == "pending" and queued.json()["width"] == 1344
        [record] = (await client.get(f"/api/chats/{ids['chat_id']}/illustrations")).json()
        assert record["status"] == "ready", record
        assert record["media_type"] == "image/png" and list(record["prompt"]) == ["prompt"]
        image = await client.get(f"/api/chats/{ids['chat_id']}/illustrations/{record['id']}/image")
        assert image.status_code == 200 and image.content == PNG
        assert "immutable" in image.headers["cache-control"]

        hidden = await client.patch(f"/api/chats/{ids['chat_id']}/illustrations/{record['id']}", json={"hidden": True})
        assert hidden.json()["hidden"] is True
        assert (await client.delete(f"/api/chats/{ids['chat_id']}/image-workflows/{workflow['id']}")).status_code == 409

        queued_body = json.loads(comfy_calls[0].content)
        assert queued_body["prompt"]["3"]["inputs"]["seed"] == record["seed"]
        prompt = queued_body["prompt"]["6"]["inputs"]["text"]
        assert prompt == "masterpiece, " + record["prompt"]["prompt"]
        assert "## 用户输入\n我问她为什么这么晚" in prompt and "地点: 校门外" in prompt and "## 中心人物\n角色\n" in prompt
        assert "她坐在车后座上。" in prompt and "<think>" not in prompt

        assert (await client.delete(f"/api/chats/{ids['chat_id']}")).status_code == 204
        assert not (tmp_path / "images" / ids["chat_id"]).exists()
    run(database, tmp_path, scenario, comfy=comfy_handler(comfy_calls))
    assert (tmp_path / "images").exists()


@pytest.mark.parametrize("options, message", [
    ({"reject": True}, "ComfyUI 拒绝了工作流：Prompt outputs failed validation；节点 6（CLIPTextEncode）：Required input is missing clip"),
    ({"history_error": True}, "ComfyUI 执行失败：节点 KSampler：CUDA out of memory"),
])
def test_failures_are_recorded_and_retry_adds_an_attempt(database, illustrated_chat, tmp_path, options, message):
    ids = illustrated_chat
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        await setup_workflow(client, ids["chat_id"])
        url = f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations"
        assert (await client.post(url)).status_code == 202
        assert (await client.post(url)).status_code == 202
        records = (await client.get(f"/api/chats/{ids['chat_id']}/illustrations")).json()
        assert [r["status"] for r in records] == ["failed", "failed"]
        assert records[0]["error"] == message and "## 用户输入" in records[0]["prompt"]["prompt"]
        assert (await client.get(f"/api/chats/{ids['chat_id']}/illustrations/{records[0]['id']}/image")).status_code == 404
    run(database, tmp_path, scenario, comfy=comfy_handler([], **options))


def test_a_stored_workflow_with_old_placeholders_fails_before_comfyui(database, illustrated_chat, tmp_path):
    ids, comfy_calls = illustrated_chat, []
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        workflow = await setup_workflow(client, ids["chat_id"])
        with database.transaction() as session:  # Older rows and data management aren't validated by the API.
            session.get(ImageWorkflow, workflow["id"]).workflow = {
                **WORKFLOW, "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative_prompt}}"}}}
        await client.post(f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations")
        [record] = (await client.get(f"/api/chats/{ids['chat_id']}/illustrations")).json()
        assert record["status"] == "failed" and "{{negative_prompt}}" in record["error"]
    run(database, tmp_path, scenario, comfy=comfy_handler(comfy_calls))
    assert comfy_calls == []


def test_prompt_preview_and_preconditions_change_nothing(database, illustrated_chat, tmp_path):
    ids = illustrated_chat
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        url = f"/api/chats/{ids['chat_id']}/rounds/{round_id}"
        assert (await client.post(url + "/illustrations")).json()["detail"] == "聊天未开启插图"
        workflow = await setup_workflow(client, ids["chat_id"])
        before = database_contents(database)
        preview = await client.post(url + "/illustration-prompt")
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert (body["image_workflow_id"], body["focus"], body["images"]) == (workflow["id"], ["角色"], [])
        assert body["prompt"].startswith("## 用户输入\n")
        assert database_contents(database) == before
        bad = await client.post(f"/api/chats/{ids['chat_id']}/image-workflows", json={
            "name": "坏", "base_url": "http://127.0.0.1:8188", "workflow": {"1": {"class_type": "SaveImage", "inputs": {}}}})
        assert bad.status_code == 422
    run(database, tmp_path, scenario)


def test_auto_modes_after_archive(database, illustrated_chat, tmp_path):
    ids = illustrated_chat

    async def scenario(client):
        await setup_workflow(client, ids["chat_id"], mode="scene_change")
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


class FakeSocket:
    def __init__(self, messages):
        self.messages, self.closed = list(messages), False

    def recv(self, timeout):
        if not self.messages:
            raise TimeoutError
        item = self.messages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


def finishing_comfy(request):
    if request.url.path == "/prompt":
        return httpx.Response(200, json={"prompt_id": "p"})
    if request.url.path == "/history/p":
        return httpx.Response(200, json={"p": {"outputs": {"9": {"images": [{"filename": "a.png"}]}}}} if finishing_comfy.done else {})
    return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})


def event(kind, **data):
    return json.dumps({"type": kind, "data": {"prompt_id": "p", **data}})


def render_with_socket(socket, connect=None):
    reports, polls = [], []

    def report(progress):
        reports.append(progress)

    def comfy(request):
        if request.url.path == "/history/p":
            polls.append(1)
            finishing_comfy.done = len(polls) > 1
        return finishing_comfy(request)
    client = ComfyUIClient(transport=httpx.MockTransport(comfy), poll_seconds=0.01, connect=connect or (lambda url: socket))
    image = client.render("http://127.0.0.1:8188", {
        "164": {"class_type": "KSampler", "inputs": {}, "_meta": {"title": "K采样器"}},
        "169": {"class_type": "VAEDecode", "inputs": {}},
    }, report)
    assert image.data == PNG
    return reports


def test_socket_reports_progress_of_this_prompt_only():
    socket = FakeSocket([
        event("execution_start"),
        event("executing", node="164"),
        event("progress", node="164", value=3, max=12),
        json.dumps({"type": "progress", "data": {"prompt_id": "other", "node": "164", "value": 9, "max": 9}}),
        b"\x00\x00\x00\x01preview",
        "not json",
        event("executing", node="169"),
        event("executing", node=None),
    ])
    assert render_with_socket(socket) == [
        RenderProgress(queued=True), RenderProgress(), RenderProgress(node="K采样器"),
        RenderProgress(node="K采样器", value=3, max=12), RenderProgress(node="VAEDecode"),
    ]
    assert socket.closed


def test_lost_or_missing_socket_still_finishes_from_history():
    socket = FakeSocket([event("progress", node="164", value=1, max=12), OSError("gone")])
    assert render_with_socket(socket)[-1] == RenderProgress()  # The display doesn't freeze on the last step.
    assert socket.closed

    def refuse(url):
        assert url.startswith("ws://127.0.0.1:8188/ws?clientId=lorenook-")
        raise ConnectionRefusedError
    assert render_with_socket(None, refuse) == []


def test_interrupted_job_says_so():
    def comfy(request):
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "p"})
        return httpx.Response(200, json={"p": {"outputs": {}, "status": {"status_str": "error", "messages": [
            ["execution_interrupted", {"node_type": "KSampler"}]]}}})
    with pytest.raises(IllustrationError, match="被中断"):
        ComfyUIClient(transport=httpx.MockTransport(comfy)).render("http://127.0.0.1:8188", WORKFLOW)


def test_progress_stream_follows_the_board_and_ends_when_idle():
    board = ProgressBoard()
    board.set("job", "chat", IllustrationProgress(status="rendering", node="K采样器", value=1, max=12))
    board.set("elsewhere", "other", IllustrationProgress(status="pending"))

    async def main():
        stream = progress_events(board, "chat")
        first = json.loads((await anext(stream)).removeprefix("data: "))
        assert first == {"job": {"status": "rendering", "queued": False, "node": "K采样器", "value": 1, "max": 12}}
        # From another thread, as the worker does.
        await asyncio.to_thread(board.set, "job", "chat", IllustrationProgress(status="rendering", value=2, max=12))
        second = json.loads((await asyncio.wait_for(anext(stream), 2)).removeprefix("data: "))
        assert second["job"]["value"] == 2
        await asyncio.to_thread(board.clear, "job")
        assert json.loads((await asyncio.wait_for(anext(stream), 2)).removeprefix("data: ")) == {}
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    asyncio.run(main())
    assert board._listeners == set()


def test_progress_endpoint_and_job_lifecycle(database, illustrated_chat, tmp_path):
    ids = illustrated_chat
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        await setup_workflow(client, ids["chat_id"])
        missing = await client.get("/api/chats/nope/illustrations/progress")
        assert missing.status_code == 404
        await client.post(f"/api/chats/{ids['chat_id']}/rounds/{round_id}/illustrations")
        # The inline job has finished, so the board is empty again and the stream ends at once.
        stream = await client.get(f"/api/chats/{ids['chat_id']}/illustrations/progress")
        assert stream.status_code == 200 and stream.text == "data: {}\n\n"
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "no-transform" in stream.headers["cache-control"]
    run(database, tmp_path, scenario, comfy=comfy_handler([]))


def test_chat_setup_import_and_cast_copy(database, tmp_path):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "ABC 学园", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        workflow = (await client.post("/api/image-workflows", json={
            "name": "SDXL", "base_url": "http://127.0.0.1:8188", "workflow": WORKFLOW, "width": 832, "height": 1216})).json()
        cast = await client.put(f"/api/characters/{character['id']}/cast", json={"members": [
            {"name": "小明", "appearance": "short hair"}, {"name": "小红", "appearance": "long hair"}]})
        assert cast.status_code == 200, cast.text
        kept = cast.json()[1]
        again = await client.put(f"/api/characters/{character['id']}/cast", json={"members": [
            {**kept, "appearance": "long black hair"}]})
        assert again.json() == [{**kept, "appearance": "long black hair"}]  # An edit keeps the id.
        assert (await client.put(f"/api/user-identities/{identity['id']}/appearance", json={"appearance": "眼镜"})).status_code == 200

        created = (await client.post("/api/chats", json={
            "title": "新聊天", "character_id": character["id"], "user_identity_id": identity["id"]})).json()
        chat = f"/api/chats/{created['id']}"
        assert (await client.get(chat + "/illustration-settings")).json()["mode"] == "off"
        [member] = (await client.get(chat + "/cast")).json()
        assert member["name"] == "小红" and member["id"] != kept["id"]
        assert (await client.get(chat + "/appearance")).json()["appearance"] == "眼镜"
        options = (await client.get(chat + "/focus-options")).json()
        assert [o["name"] for o in options["options"]] == ["小红", "身份"] and options["default"] == []
        assert [o["has_appearance"] for o in options["options"]] == [True, True]

        settings = await client.post(chat + "/illustration-setup", json={
            "mode": "scene_change", "image_workflow_id": workflow["id"]})
        assert settings.status_code == 200, settings.text
        [copy] = (await client.get(chat + "/image-workflows")).json()
        assert copy["id"] != workflow["id"] and copy["height"] == 1216
        assert settings.json() == {"mode": "scene_change", "image_workflow_id": copy["id"], "focus": []}
        assert (await client.post(chat + "/image-workflows/import", json={"source_id": workflow["id"]})).status_code == 201
        assert len((await client.get(chat + "/image-workflows")).json()) == 2
    run(database, tmp_path, scenario)


def test_focus_defaults_overrides_and_soft_limit(database, illustrated_chat, tmp_path):
    ids = illustrated_chat
    round_id = archived_round(database, ids["chat_id"])

    async def scenario(client):
        chat = f"/api/chats/{ids['chat_id']}"
        workflow = await setup_workflow(client, ids["chat_id"])

        async def preview():
            return (await client.post(f"{chat}/rounds/{round_id}/illustration-prompt")).json()

        # No cast: the character card itself is the default, and it has no description.
        assert (await preview())["focus"] == ["角色"]
        options = (await client.get(chat + "/focus-options")).json()["options"]
        assert [(o["name"], o["has_appearance"]) for o in options] == [("角色", False), ("身份", False)]
        members = (await client.put(chat + "/cast", json={"members": [
            {"name": "甲", "appearance": "tall"}, {"name": "乙", "appearance": "short"}, {"name": "丙"}]})).json()
        # With a cast: no default, the workflow is asked to decide from the story; the card's name is no longer offered.
        first = await preview()
        assert first["focus"] == [] and "## 中心人物\n（未指定。请根据剧情内容自行判断本画面的中心人物。）\n" in first["prompt"]
        assert "<甲>\ntall\n</甲>\n<乙>\nshort\n</乙>" in first["prompt"] and "<丙>" not in first["prompt"]
        # The chat's manual choice overrides the default; a removed id is dropped.
        await client.put(chat + "/illustration-settings", json={
            "mode": "manual", "image_workflow_id": workflow["id"], "focus": [members[1]["id"], "user", "gone"]})
        chosen = await preview()
        assert chosen["focus"] == ["乙", "身份"] and "## 中心人物\n乙、身份\n" in chosen["prompt"]
        # One attempt can override again, and more than two is allowed.
        everyone = [m["id"] for m in members] + ["user"]
        queued = await client.post(f"{chat}/rounds/{round_id}/illustrations", json={"focus": everyone})
        assert [p["name"] for p in queued.json()["focus"]] == ["甲", "乙", "丙", "身份"]
    run(database, tmp_path, scenario, comfy=comfy_handler([]))


def test_reference_images_are_uploaded_and_sent_as_a_string(database, illustrated_chat, tmp_path):
    ids, comfy_calls = illustrated_chat, []
    round_id = archived_round(database, ids["chat_id"])
    plain = comfy_handler(comfy_calls)

    def comfy(request):
        if request.url.path == "/upload/image":
            comfy_calls.append(request)
            assert b'name="overwrite"' in request.content and PNG in request.content
            return httpx.Response(200, json={"name": "ref.png", "subfolder": "lore", "type": "input"})
        return plain(request)

    def queued():
        return json.loads([c for c in comfy_calls if c.url.path == "/prompt"][-1].content)["prompt"]

    async def scenario(client):
        chat = f"/api/chats/{ids['chat_id']}"
        assert (await client.post("/api/media", content=b"not an image")).status_code == 415
        uploaded = await client.post("/api/media", content=PNG)
        assert uploaded.status_code == 201, uploaded.text
        name = uploaded.json()["name"]
        served = await client.get(uploaded.json()["url"])
        assert served.content == PNG and served.headers["content-type"] == "image/png"
        assert (await client.get("/api/media/..%2Fsecret.png")).status_code == 404

        workflow = await setup_workflow(client, ids["chat_id"], workflow=IMAGES_WORKFLOW)
        await client.put(chat + "/cast", json={"members": [{"name": "甲", "appearance": "tall"}]})
        url = f"{chat}/rounds/{round_id}/illustrations"

        # No reference image is not an error: the workflow just receives an empty list.
        await client.post(url)
        record = (await client.get(chat + "/illustrations")).json()[-1]
        assert record["status"] == "ready", record
        assert queued()["10"]["inputs"]["images"] == "[]" and "/upload/image" not in [c.url.path for c in comfy_calls]

        members = (await client.get(chat + "/cast")).json()
        assert (await client.put(chat + "/cast", json={"members": [{**members[0], "reference_image": "../x.png"}]})).status_code == 422
        await client.put(chat + "/cast", json={"members": [{**members[0], "reference_image": name}]})
        await client.post(url)
        record = (await client.get(chat + "/illustrations")).json()[-1]
        assert record["status"] == "ready", record
        assert queued()["10"]["inputs"]["images"] == '["lore/ref.png"]'
        assert "<甲>\n参考图：图 1\ntall\n</甲>" in record["prompt"]["prompt"]

        # A workflow that takes no images gets no upload and no numbering.
        await client.patch(f"{chat}/image-workflows/{workflow['id']}", json={"workflow": WORKFLOW})
        uploads = [c for c in comfy_calls if c.url.path == "/upload/image"]
        await client.post(url)
        record = (await client.get(chat + "/illustrations")).json()[-1]
        assert "参考图" not in record["prompt"]["prompt"]
        assert [c for c in comfy_calls if c.url.path == "/upload/image"] == uploads
    run(database, tmp_path, scenario, comfy=comfy)
