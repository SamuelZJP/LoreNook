import contextvars
from backend.tests.state_fixtures import WORLD
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
import re

import httpx
import pytest

from backend.llm.client import ModelClient
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Character, Chat, ChatModelBinding, ModelConfig, Round, WritingPreset
from backend.repository.queries import Repository
from backend.schemas.archive import ArchiveConfirm, RoundScene
from backend.shared.errors import ArchiveExecutionError, ConflictError
from backend.tests.test_catalog_api import run_api
from backend.tests.test_writing import database_contents
from backend.workflows.archive import confirm_archive, retry_archive

INPUT = " 用户原文\r\n"
OUTPUT = " <report_nya~>自定义思考</report_nya~>\r\n<content>本回合正文</content>\n"
SUMMARY = " 2026/10/19—08:01—教室\n摘要原文\r\n"
EPISODE = " 2026/10/19—2026/10/19—教室\n角色与用户在连续几轮对话中交换消息，确认此前的计划与约定。\r\n"


def response(text):
    if text == EPISODE:
        text = json.dumps({"title": "测试事件", "summary": text}, ensure_ascii=False)
    return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]})


@pytest.fixture
def archive_chat(database, chat):
    with database.transaction() as session:
        repo = Repository(session)
        model = repo.add(ModelConfig(chat_id=chat[0], name="归档模型", api_type="google_generate_content",
                                    base_url="https://provider.test/v1beta", api_key="archive-secret", model="test"))
        for purpose in ("state_update", "round_summary", "episode_summary"):
            repo.add(ChatModelBinding(chat_id=chat[0], purpose=purpose, model_config_id=model.id))
    return chat[0]


def payload(previous=None):
    return {"user_input": INPUT, "ai_output": OUTPUT, "based_on_round_id": previous}


def step_of(request):
    system = json.loads(request.content)["systemInstruction"]["parts"][0]["text"]
    if "JSON Patch" in system:
        return "state_update"
    if "连续回合" in system:
        return "episode_summary"
    return "round_summary"


def successful_handler(calls, *, new_day=False):
    def handler(request):
        step = step_of(request)
        calls.append(step)
        if step == "state_update":
            prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
            hour, minute = map(int, re.search(r"时间: ['\"]?(\d{2}):(\d{2})", prompt).groups())
            patch = json.dumps([{"op": "replace", "path": "/世界/日期", "value": "2026-10-20"}] if new_day
                               else [{"op": "replace", "path": "/世界/时间", "value": f"{hour:02}:{(minute + 1) % 60:02}"}], ensure_ascii=False)
            return response('<UpdateVariable><Analysis>本轮结算。</Analysis><JSONPatch>' + patch +
                            '</JSONPatch></UpdateVariable>')
        return response(EPISODE if step == "episode_summary" else SUMMARY)
    return handler


def test_round_scene_comes_from_its_state_world():
    assert RoundScene.from_world(None) is None
    assert RoundScene.from_world({"日期": "2026-10-19", "时间": 3, "地点": "很长很长的地点名称——校门外的林荫道尽头"}) == RoundScene(
        date="2026-10-19", place="很长很长的地点名称——校门外的林荫道尽头")


def seed_history(database, chat_id, count=5):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        ids = []
        for number in range(1, count + 1):
            record = repo.create_round(chat_id, f"旧输入{number}", "<content>旧正文</content>")
            ids.append(record.id)
            repo.save_state(record.id, {"世界": dict(WORLD)})
            repo.save_summary(record.id, f"旧摘要{number}")
            repo.save_decision(record.id)
        return ids


def test_confirmation_runs_all_steps_and_preserves_original_text(database, archive_chat):
    calls, chat_id = [], archive_chat
    base_handler = successful_handler(calls)
    def handler(request):
        assert database.engine.pool.checkedout() == 0
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "本回合正文" in prompt and "自定义思考" not in prompt and "report_nya" not in prompt
        return base_handler(request)
    async def scenario(client):
        root = f"/api/chats/{chat_id}"
        assert (await client.get(root + "/archive")).json() is None
        assert (await client.get(root + "/rounds")).json() == []
        result = await client.post(root + "/archive", json=payload())
        assert result.status_code == 201, result.text
        progress = result.json()
        record = progress["round"]
        assert record["round_no"] == 1 and record["archive_step"] == "complete"
        assert record["user_input"] == INPUT and record["ai_output"] == OUTPUT
        assert record["summary"] == SUMMARY and record["archive_error"] is None
        assert record["episode_required"] is False and progress["episode"] is None
        assert progress["state"]["round_id"] == record["id"]
        world = progress["state"]["content"]["世界"]
        assert record["scene"] == {"date": world["日期"], "time": world["时间"], "place": world["地点"]}
        assert (await client.get(root + "/archive")).json() == progress
        assert (await client.get(root + f"/rounds/{record['id']}")).json() == progress
        assert (await client.get(root + "/rounds")).json() == [record]
        assert (await client.post(root + "/archive", json=payload())).status_code == 409
        retry = root + f"/rounds/{record['id']}/archive/retry"
        assert (await client.post(retry, json={"expected_step": "state_update"})).status_code == 409
        # Explicitly confirming a new candidate must name the completed predecessor.
        second = await client.post(root + "/archive", json=payload(record["id"]))
        assert second.status_code == 201 and second.json()["round"]["round_no"] == 2
        assert [r["round_no"] for r in (await client.get(root + "/rounds")).json()] == [1, 2]
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert calls == ["state_update", "round_summary"] * 2


def test_confirmation_generates_episode_only_when_required(database, archive_chat):
    previous = seed_history(database, archive_chat)
    calls = []
    async def scenario(client):
        result = await client.post(f"/api/chats/{archive_chat}/archive", json=payload(previous[-1]))
        assert result.status_code == 201, result.text
        progress = result.json()
        assert progress["round"]["archive_step"] == "complete"
        assert progress["round"]["episode_required"] is True
        assert progress["episode"]["summary"] == EPISODE
        assert progress["episode"]["start_round_id"] == previous[0]
        assert progress["episode"]["end_round_id"] == previous[-1]
        assert progress["episode"]["created_by_round_id"] == progress["round"]["id"]
    run_api(database, scenario, llm_transport=httpx.MockTransport(successful_handler(calls, new_day=True)))
    assert calls == ["state_update", "round_summary", "episode_summary"]


@pytest.mark.parametrize("failed_step", ["state_update", "round_summary", "episode_summary"])
@pytest.mark.parametrize("failure_kind", ["http", "invalid_content"])
def test_generation_failure_returns_progress_and_retry_skips_successful_steps(database, archive_chat, failed_step, failure_kind):
    previous = seed_history(database, archive_chat) if failed_step == "episode_summary" else []
    calls, failed = [], False
    good = successful_handler(calls, new_day=bool(previous))
    def handler(request):
        nonlocal failed
        step = step_of(request)
        if step == failed_step and not failed:
            failed = True
            calls.append(step)
            if failure_kind == "invalid_content":
                text = ('<UpdateVariable><Analysis>无变化。</Analysis><JSONPatch>[]</JSONPatch></UpdateVariable>'
                        if step == "state_update" else json.dumps({"title": "事件", "summary": "略"})
                        if step == "episode_summary" else "略")
                return response(text)
            return httpx.Response(429, json={"error": "archive-secret"})
        return good(request)
    async def scenario(client):
        root = f"/api/chats/{archive_chat}"
        result = await client.post(root + "/archive", json=payload(previous[-1] if previous else None))
        assert result.status_code == (502 if failure_kind == "http" else 422) and "archive-secret" not in result.text
        progress = result.json()["archive"]
        record = progress["round"]
        rid = record["id"]
        assert record["archive_step"] == failed_step and record["archive_error"]
        assert record["user_input"] == INPUT and record["ai_output"] == OUTPUT
        assert (progress["state"] is None) == (failed_step == "state_update")
        assert progress["episode"] is None
        assert (await client.get(root + "/archive")).json() == progress
        before_retry = database_contents(database)
        assert (await client.post(root + "/writing", json={"user_input": "下一回合"})).status_code == 409
        assert (await client.post(root + "/archive", json=payload(rid))).status_code == 409
        assert database_contents(database) == before_retry
        result = await client.post(root + f"/rounds/{rid}/archive/retry", json={"expected_step": failed_step})
        assert result.status_code == 200, result.text
        final = result.json()
        assert final["round"]["id"] == rid and final["round"]["archive_step"] == "complete"
        assert final["round"]["archive_error"] is None
        if failed_step != "state_update":
            assert final["state"] == progress["state"]
        if failed_step == "episode_summary":
            assert final["round"]["episode_start_round_id"] == record["episode_start_round_id"]
            assert final["round"]["episode_end_round_id"] == record["episode_end_round_id"]
            assert final["round"]["summary"] == record["summary"]
        assert len((await client.get(root + "/rounds")).json()) == len(previous) + 1
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    expected = ["state_update", "round_summary", "episode_summary"] if previous else ["state_update", "round_summary"]
    index = expected.index(failed_step)
    assert calls == expected[:index + 1] + expected[index:]


def test_decision_failure_preserves_saved_results_then_resume_without_repeating_models(database, archive_chat):
    previous = seed_history(database, archive_chat)
    with database.transaction() as session:
        Repository(session).state_for_round(archive_chat, previous[-1]).content = {"世界": dict(WORLD, 日期="旧格式")}
    calls = []
    async def scenario(client):
        root = f"/api/chats/{archive_chat}"
        # An invalid legacy predecessor reaches the deterministic decision failure.
        result = await client.post(root + "/archive", json=payload(previous[-1]))
        assert result.status_code == 422, result.text
        progress = result.json()["archive"]
        rid = progress["round"]["id"]
        assert progress["round"]["archive_step"] == "episode_decision"
        assert progress["state"] is not None and progress["round"]["summary"] == SUMMARY
        with database.transaction() as session:
            repo = Repository(session)
            repo.state_for_round(archive_chat, previous[-1]).content = {"世界": dict(WORLD)}
        final = await client.post(root + f"/rounds/{rid}/archive/retry", json={"expected_step": "episode_decision"})
        assert final.status_code == 200 and final.json()["round"]["archive_step"] == "complete"
        assert final.json()["episode"]["summary"] == EPISODE
    def handler(request):
        step = step_of(request)
        calls.append(step)
        return response('<UpdateVariable><Analysis>跨日。</Analysis><JSONPatch>'
                        '[{"op":"replace","path":"/世界/日期","value":"2026-10-20"}]'
                        '</JSONPatch></UpdateVariable>' if step == "state_update"
                        else EPISODE if step == "episode_summary" else SUMMARY)
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert calls == ["state_update", "round_summary", "episode_summary"]


@pytest.mark.parametrize("body", [
    {"user_input": INPUT, "ai_output": OUTPUT},
    {"user_input": 1, "ai_output": OUTPUT, "based_on_round_id": None},
    {"user_input": INPUT, "ai_output": " ", "based_on_round_id": None},
    {**payload(), "archive_step": "complete"},
    {**payload(), "ai_output": "正文缺标签"},
    {**payload(), "ai_output": "<content> </content>"},
    {**payload(), "ai_output": "</content>正文<content>"},
    {**payload(), "ai_output": "<content>一</content><content>二</content>"},
])
def test_invalid_confirmation_does_not_save_or_call_model(database, archive_chat, body):
    before, calls = database_contents(database), []
    async def scenario(client):
        result = await client.post(f"/api/chats/{archive_chat}/archive", json=body)
        assert result.status_code == 422, result.text
        assert "archive" not in result.json()
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == [] and database_contents(database) == before


@pytest.mark.parametrize("previous", ["missing", "other_chat"])
def test_stale_or_foreign_predecessor_is_rejected(database, archive_chat, previous):
    other_id = "missing"
    if previous == "other_chat":
        with database.transaction() as session:
            repo = ArchiveRepository(session)
            other = repo.add(Chat(title="其他聊天"))
            other_id = repo.create_round(other.id, "输入", "输出").id
    before = database_contents(database)
    async def scenario(client):
        result = await client.post(f"/api/chats/{archive_chat}/archive", json=payload(other_id))
        assert result.status_code == 409
    run_api(database, scenario)
    assert database_contents(database) == before


def test_scope_and_stale_retry_do_not_write_or_call(database, archive_chat):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        rid = repo.create_round(archive_chat, INPUT, OUTPUT).id
        other = repo.add(Chat(title="其他聊天")).id
    before, calls = database_contents(database), []
    async def scenario(client):
        for root in ("/api/chats/missing", f"/api/chats/{other}"):
            assert (await client.get(root + f"/rounds/{rid}")).status_code == 404
            assert (await client.post(root + f"/rounds/{rid}/archive/retry", json={"expected_step": "state_update"})).status_code == 404
        root = f"/api/chats/{archive_chat}"
        assert (await client.post("/api/chats/missing/archive", json=payload())).status_code == 404
        retry = root + f"/rounds/{rid}/archive/retry"
        assert (await client.post(retry, json={"expected_step": "round_summary"})).status_code == 409
        for invalid in ({}, {"expected_step": "complete"}, {"expected_step": "state_update", "ai_output": "覆盖"}):
            assert (await client.post(retry, json=invalid)).status_code == 422
        assert (await client.get(root + "/archive")).json()["state"] is None
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == [] and database_contents(database) == before


@pytest.mark.parametrize("step", ["state_update", "round_summary", "episode_decision", "episode_summary"])
def test_resume_after_process_interruption_at_any_step(database, archive_chat, step):
    previous = seed_history(database, archive_chat) if step == "episode_summary" else []
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        rid = repo.create_round(archive_chat, INPUT, OUTPUT).id
        if step != "state_update":
            repo.save_state(rid, {"世界": {"日期": "2026-10-20"}})
        if step in ("episode_decision", "episode_summary"):
            repo.save_summary(rid, SUMMARY)
        if step == "episode_summary":
            repo.save_decision(rid, start_round_id=previous[0], end_round_id=previous[-1])
    calls = []
    async def scenario(client):
        root = f"/api/chats/{archive_chat}"
        progress = (await client.get(root + "/archive")).json()
        assert progress["round"]["archive_step"] == step and progress["round"]["archive_error"] is None
        result = await client.post(root + f"/rounds/{rid}/archive/retry", json={"expected_step": step})
        assert result.status_code == 200 and result.json()["round"]["id"] == rid
        assert result.json()["round"]["archive_step"] == "complete"
    run_api(database, scenario, llm_transport=httpx.MockTransport(successful_handler(calls)))
    expected = {"state_update": ["state_update", "round_summary"], "round_summary": ["round_summary"],
                "episode_decision": [], "episode_summary": ["episode_summary"]}
    assert calls == expected[step]


def test_concurrent_confirmation_creates_one_round_even_if_it_finishes_before_duplicate(database, archive_chat):
    barrier, calls = Barrier(2), []
    model_client = ModelClient(transport=httpx.MockTransport(successful_handler(calls)))
    def confirm():
        barrier.wait(timeout=5)
        try:
            return confirm_archive(database, model_client, archive_chat, ArchiveConfirm(**payload())).round.archive_step
        except ConflictError:
            return "conflict"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda context: context.run(confirm), [contextvars.copy_context() for _ in range(2)]))
    finally:
        model_client.close()
    assert sorted(results) == ["complete", "conflict"]
    assert calls == ["state_update", "round_summary"]
    with database.read() as session:
        assert len(Repository(session).rounds(archive_chat)) == 1


def test_confirmation_transaction_failure_leaves_no_round(database, archive_chat, monkeypatch):
    before = database_contents(database)
    original = ArchiveRepository.create_round
    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("正文保存事务中断")
    monkeypatch.setattr(ArchiveRepository, "create_round", fail)
    client = ModelClient(transport=httpx.MockTransport(lambda request: pytest.fail("不应调用模型")))
    try:
        with pytest.raises(RuntimeError):
            confirm_archive(database, client, archive_chat, ArchiveConfirm(**payload()))
    finally:
        client.close()
    assert database_contents(database) == before


def test_writing_candidate_can_be_confirmed_without_rerunning_its_preset(database, archive_chat):
    from backend.tests.test_writing import SOURCE
    with database.transaction() as session:
        repo = Repository(session)
        preset = repo.add(WritingPreset(chat_id=archive_chat, name="写作", source=SOURCE))
        repo.get(Chat, archive_chat).writing_preset_id = preset.id
        preset_id = preset.id
        model_id = repo.model_binding(archive_chat, "state_update").model_config_id
        repo.add(ChatModelBinding(chat_id=archive_chat, purpose="writing", model_config_id=model_id))
    calls = []
    good = successful_handler(calls)
    def handler(request):
        if "systemInstruction" not in json.loads(request.content):
            calls.append("writing")
            return httpx.Response(200, json={"text": OUTPUT})
        return good(request)
    before = database_contents(database)
    async def scenario(client):
        root = f"/api/chats/{archive_chat}"
        writing = await client.post(root + "/writing", json={"user_input": INPUT})
        assert writing.status_code == 200
        candidate = writing.json()
        assert database_contents(database) == before
        with database.transaction() as session:
            Repository(session).get(WritingPreset, preset_id).source = "broken("
        confirmation = {key: candidate[key] for key in ("user_input", "ai_output", "based_on_round_id")}
        result = await client.post(root + "/archive", json=confirmation)
        assert result.status_code == 201, result.text
        assert result.json()["round"]["ai_output"] == candidate["ai_output"]
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert calls == ["writing", "state_update", "round_summary"]


def test_instruction_only_reaches_the_writing_request(database, archive_chat):
    from backend.tests.test_writing import SOURCE
    instruction = "让剧情转向雨夜"
    with database.transaction() as session:
        repo = Repository(session)
        preset = repo.add(WritingPreset(chat_id=archive_chat, name="写作", source=SOURCE))
        repo.get(Chat, archive_chat).writing_preset_id = preset.id
        model_id = repo.model_binding(archive_chat, "state_update").model_config_id
        repo.add(ChatModelBinding(chat_id=archive_chat, purpose="writing", model_config_id=model_id))
    calls, archive_prompts = [], []
    good = successful_handler(calls)
    def handler(request):
        body = json.loads(request.content)
        if "systemInstruction" not in body:
            materials = json.loads(body["contents"][0]["parts"][0]["text"])
            assert materials["user_input"] == f"{INPUT}\n\n<instruction>\n{instruction}\n</instruction>"
            calls.append("writing")
            return httpx.Response(200, json={"text": OUTPUT})
        archive_prompts.append(json.dumps(body, ensure_ascii=False))
        return good(request)
    async def scenario(client):
        root = f"/api/chats/{archive_chat}"
        preview = await client.post(root + "/writing-preview", json={"user_input": INPUT, "instruction": instruction})
        assert instruction in json.loads(preview.json()["request"]["body"]["contents"][0]["parts"][0]["text"])["user_input"]
        writing = await client.post(root + "/writing", json={"user_input": INPUT, "instruction": instruction})
        assert writing.status_code == 200, writing.text
        candidate = writing.json()
        assert candidate["user_input"] == INPUT
        confirmation = {key: candidate[key] for key in ("user_input", "ai_output", "based_on_round_id")}
        result = await client.post(root + "/archive", json=confirmation)
        assert result.status_code == 201, result.text
        following = await client.post(root + "/writing-preview", json={"user_input": "下一回合"})
        assert instruction not in following.json()["request"]["body"]["contents"][0]["parts"][0]["text"]
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert calls == ["writing", "state_update", "round_summary"]
    assert len(archive_prompts) == 2 and not any(instruction in prompt for prompt in archive_prompts)
    assert instruction not in str(database_contents(database))


@pytest.mark.parametrize("failure,status,step", [("state_binding", 409, "state_update"),
    ("summary_binding", 409, "round_summary"), ("api_type", 422, "state_update"), ("schema", 422, "state_update")])
def test_configuration_can_be_repaired_after_confirmation(database, archive_chat, failure, status, step):
    with database.transaction() as session:
        repo = Repository(session)
        model_id = repo.model_binding(archive_chat, "state_update").model_config_id
        character_id = repo.list_owned(Character, archive_chat)[0].id
        if failure.endswith("binding"):
            repo.delete(repo.model_binding(archive_chat, "state_update" if failure == "state_binding" else "round_summary"))
        elif failure == "api_type":
            repo.get(ModelConfig, model_id).api_type = "unsupported"
        else:
            repo.get(Character, character_id).state_schema = "broken schema"
    calls = []
    async def scenario(client):
        root = f"/api/chats/{archive_chat}"
        result = await client.post(root + "/archive", json=payload())
        assert result.status_code == status, result.text
        progress = result.json()["archive"]
        rid = progress["round"]["id"]
        assert progress["round"]["archive_step"] == step
        with database.transaction() as session:
            repo = Repository(session)
            if failure.endswith("binding"):
                purpose = "state_update" if failure == "state_binding" else "round_summary"
                repo.add(ChatModelBinding(chat_id=archive_chat, purpose=purpose, model_config_id=model_id))
            elif failure == "api_type":
                repo.get(ModelConfig, model_id).api_type = "google_generate_content"
            else:
                repo.get(Character, character_id).state_schema = ""
        result = await client.post(root + f"/rounds/{rid}/archive/retry", json={"expected_step": step})
        assert result.status_code == 200 and result.json()["round"]["archive_step"] == "complete"
        assert result.json()["round"]["archive_error"] is None
        assert len((await client.get(root + "/rounds")).json()) == 1
    run_api(database, scenario, llm_transport=httpx.MockTransport(successful_handler(calls)))
    # A schema is checked after generating the patch; repairing it retries that model step.
    assert calls == (["state_update"] if failure == "schema" else []) + ["state_update", "round_summary"]


def test_concurrent_retry_does_not_repeat_successful_later_steps(database, archive_chat):
    with database.transaction() as session:
        rid = ArchiveRepository(session).create_round(archive_chat, INPUT, OUTPUT).id
    barrier, calls = Barrier(2), []
    good = successful_handler(calls)
    def handler(request):
        if step_of(request) == "state_update":
            barrier.wait(timeout=5)
        return good(request)
    client = ModelClient(transport=httpx.MockTransport(handler))
    def retry():
        try:
            return retry_archive(database, client, archive_chat, rid, "state_update").round.archive_step
        except ArchiveExecutionError as error:
            assert isinstance(error.cause, ConflictError)
            return "conflict"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda context: context.run(retry), [contextvars.copy_context() for _ in range(2)]))
    finally:
        client.close()
    assert sorted(results) == ["complete", "conflict"]
    assert calls.count("state_update") == 2 and calls.count("round_summary") == 1
    with database.read() as session:
        repo = Repository(session)
        assert repo.get(Round, rid).archive_error is None
        assert len(repo.rounds(archive_chat)) == 1


def test_interruption_between_committed_steps_is_recoverable(database, archive_chat, monkeypatch):
    from backend.workflows import archive
    original, calls = archive.run_round_summary, []
    def interrupt(*args, **kwargs):
        raise RuntimeError("状态保存后进程中断")
    monkeypatch.setattr(archive, "run_round_summary", interrupt)
    client = ModelClient(transport=httpx.MockTransport(successful_handler(calls)))
    try:
        with pytest.raises(RuntimeError):
            confirm_archive(database, client, archive_chat, ArchiveConfirm(**payload()))
    finally:
        client.close()
    monkeypatch.setattr(archive, "run_round_summary", original)
    async def scenario(api_client):
        root = f"/api/chats/{archive_chat}"
        progress = (await api_client.get(root + "/archive")).json()
        rid = progress["round"]["id"]
        assert progress["round"]["archive_step"] == "round_summary"
        assert progress["round"]["archive_error"] is None
        final = await api_client.post(root + f"/rounds/{rid}/archive/retry", json={"expected_step": "round_summary"})
        assert final.status_code == 200 and final.json()["state"] == progress["state"]
    run_api(database, scenario, llm_transport=httpx.MockTransport(successful_handler(calls)))
    assert calls == ["state_update", "round_summary"]
