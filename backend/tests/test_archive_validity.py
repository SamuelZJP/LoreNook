"""BE-001: length boundaries and full JSON state comparison at generation boundaries."""

import json

import httpx
import pytest

from backend.repository.models import Character, Round
from backend.repository.archive import ArchiveRepository
from backend.repository.queries import Repository
from backend.llm.client import ModelClient
from backend.modules.episode_summary.generate import generate_episode_summary
from backend.modules.round_summary.generate import generate_summary
from backend.schemas.episode_summary import EpisodeBridgeRound
from backend.shared.errors import EpisodeSummaryError
from backend.shared.summary_length import content_length, has_numeric_start, minimum_summary_length, summary_length
from backend.tests.test_catalog_api import run_api
from backend.tests.test_round_summary import summary_round, text_response as round_response
from backend.tests.test_episode_summary import pending_episode, text_response as episode_response
from backend.tests.test_state import state_round, patch_response
from backend.tests.test_archive_workflow import archive_chat, payload, seed_history, step_of, successful_handler, response
from backend.schemas.archive import ArchiveConfirm
from backend.shared.errors import ArchiveExecutionError
from backend.workflows.archive import confirm_archive, retry_archive
from backend.workflows.episode_summary import _context as episode_context
from backend.workflows.round_summary import _context as round_context


def test_counting_and_adaptive_thresholds():
    assert content_length("你好，Ab 12\n—😀！") == 6
    assert summary_length("2026/10/20—09:30—很长的地点\r\n你好，Ab 12") == 6
    assert summary_length("2026/10/20—09:30—很长的地点") == 0
    assert summary_length("角色在2026年相遇。") == 10
    for floor, cap in [(150, 75), (200, 100)]:
        assert minimum_summary_length(["一" * 11, "！ \n"], target_floor=floor) == 3
        assert minimum_summary_length(["一" * 5000], target_floor=floor) == cap


@pytest.mark.parametrize("text,valid", [("20正文", True), (" \r\n2026正文\t", True),
    ("12随便写点内容", True), ("", False), ("1", False), ("1正文", False),
    ("２0正文", False), ("٢٠正文", False), ("以下是摘要：2026正文", False)])
def test_summary_start_requires_two_ascii_digits(text, valid):
    assert has_numeric_start(text) is valid


@pytest.mark.parametrize("kind", ["round", "episode"])
@pytest.mark.parametrize("prefix", ["", "1", "２0", "٢٠", "以下是摘要：", "```text\n", "<content>"])
def test_invalid_summary_start_preserves_progress_then_retries(database, request, kind, prefix):
    ids = request.getfixturevalue("summary_round" if kind == "round" else "pending_episode")
    calls = []
    valid = " \r\n2026/10/19—08:00—教室\n" + "事件" * 60 + "\r\n "
    def handler(request):
        calls.append(request)
        summary = prefix + "事件" * 60 if len(calls) == 1 else valid
        body = round_response(summary) if kind == "round" else episode_response(
            "```json\n" + json.dumps({"title": "2026事件", "summary": summary}) + "\n```")
        return httpx.Response(200, json=body)
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}"
        before = (await client.get(root)).json()
        path = root + ("/round-summary" if kind == "round" else "/episode-summary")
        failed = await client.post(path)
        assert failed.status_code == 422, failed.text
        progress = (await client.get(root)).json()
        error = progress["round"]["archive_error"]
        assert "两位 ASCII 数字" in error
        before["round"]["archive_error"] = error
        assert progress == before
        retry = await client.post(path)
        assert retry.status_code == 200, retry.text
        result = retry.json()
        assert (result["summary"] if kind == "round" else result["episode"]["summary"]) == valid
        assert result["archive_step"] == ("episode_decision" if kind == "round" else "complete")
        assert (await client.get(root)).json()["round"]["archive_error"] is None
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))
    assert len(calls) == 2


def test_round_source_counts_only_user_and_body(database, summary_round):
    with database.read() as session:
        context = round_context(Repository(session), summary_round["chat_id"], summary_round["round_id"], 3)
    context = context.model_copy(update={
        "user_input": "一" * 5, "ai_output": "<report>" + "报告" * 1000 + "</report><content>" + "二" * 6 + "</content>",
        "state": {"大字段": "状态" * 1000}, "summaries": ["历史" * 1000],
    })
    summary = "2026/10/19—08:00—教室\n三字长"
    client = ModelClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=round_response(summary))))
    try:
        assert generate_summary(context, client) == summary  # ceil(11 / 5) = 3
    finally:
        client.close()


@pytest.mark.parametrize("first_message,passes", [(None, True), ("首" * 10, False),
    ("<report>" + "报告" * 1000 + "</report><content>" + "首" * 10 + "</content>", False)])
def test_episode_source_includes_opening_excludes_duplicate_and_bridge(database, pending_episode, first_message, passes):
    with database.read() as session:
        context = episode_context(ArchiveRepository(session), pending_episode["chat_id"], pending_episode["round_id"])
    source = context.rounds[0].model_copy(update={
        "user_input": "一" * 5, "ai_output": "<report>" + "报告" * 1000 + "</report><content>" + "二" * 6 + "</content>",
        "summary": "重复" * 1000, "state": {"大字段": "状态" * 1000},
    })
    context = context.model_copy(update={"rounds": [source], "first_message": first_message,
        "bridge": EpisodeBridgeRound(id="bridge", round_no=0, summary="旧摘要" * 1000,
                                     user_input="旧输入" * 1000, ai_output="<content>" + "旧正文" * 1000 + "</content>")})
    summary = "2026/10/19—2026/10/19—教室\n三字长"
    body = episode_response(json.dumps({"title": "完整标题不会计入正文", "summary": summary}))
    client = ModelClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    try:
        if passes:
            assert generate_episode_summary(context, client).summary == summary
        else:
            with pytest.raises(EpisodeSummaryError, match="最低要求 5"):
                generate_episode_summary(context, client)
    finally:
        client.close()


@pytest.mark.parametrize("kind,cap", [("round", 75), ("episode", 100)])
@pytest.mark.parametrize("offset", [-1, 0])
def test_summary_boundary_preserves_prior_results_and_retries(database, request, kind, cap, offset):
    ids = request.getfixturevalue("summary_round" if kind == "round" else "pending_episode")
    with database.transaction() as session:
        repo = Repository(session)
        source_id = ids["round_id"] if kind == "round" else ids["ids"][0]
        repo.get(Round, source_id).user_input = "事实" * 600
    calls = []
    header = "2026/10/19—2026/10/20—教室\n"
    def handler(request):
        calls.append(request)
        text = header + "事" * (cap + offset if len(calls) == 1 else cap)
        body = round_response(text) if kind == "round" else episode_response(json.dumps({"title": "事件", "summary": text}))
        return httpx.Response(200, json=body)
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}"
        before = (await client.get(root)).json()
        path = root + ("/round-summary" if kind == "round" else "/episode-summary")
        result = await client.post(path)
        if offset < 0:
            assert result.status_code == 422, result.text
            failed = (await client.get(root)).json()
            assert failed["state"] == before["state"]
            assert failed["episode"] is None
            for field in ("archive_step", "summary", "episode_start_round_id", "episode_end_round_id"):
                assert failed["round"][field] == before["round"][field]
            assert f"最低要求 {cap}" in failed["round"]["archive_error"]
            result = await client.post(path)
        assert result.status_code == 200, result.text
        final = (await client.get(root)).json()
        assert final["round"]["archive_error"] is None
        assert final["round"]["archive_step"] == ("episode_decision" if kind == "round" else "complete")
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("old,new", [(1, True), (1, 1.0), ([1, 2], [2, 1]), ({"a": 1}, {"a": True})])
def test_state_json_types_and_array_order_are_real_changes(database, state_round, old, new):
    chat_id, character_id, rid = state_round
    with database.transaction() as session:
        repo = Repository(session)
        repo.get(Character, character_id).state_schema = ""
        state = repo.latest_state(character_id)
        state.content = state.content | {"测试": old}
    async def scenario(client):
        result = await client.post(f"/api/chats/{chat_id}/rounds/{rid}/state-update")
        assert result.status_code == 200, result.text
        assert json.dumps(result.json()["state"]["content"]["测试"]) == json.dumps(new)
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: httpx.Response(200, json=patch_response([
        {"op": "replace", "path": "/测试", "value": new}]))))


@pytest.mark.parametrize("step,error_type", [("state_update", "StateUpdateError"),
    ("round_summary", "RoundSummaryError"), ("episode_summary", "EpisodeSummaryError")])
def test_invalid_content_records_workflow_failure_and_retry_attempt(database, archive_chat, tmp_path, step, error_type):
    previous = seed_history(database, archive_chat) if step == "episode_summary" else []
    calls, failed = [], False
    good = successful_handler(calls, new_day=bool(previous))
    def handler(request):
        nonlocal failed
        if step_of(request) == step and not failed:
            failed = True
            calls.append(step)
            if step == "state_update":
                return httpx.Response(200, json=patch_response([]))
            return response(json.dumps({"title": "事件", "summary": "略"}) if step == "episode_summary" else "略")
        return good(request)
    client = ModelClient(transport=httpx.MockTransport(handler), recording_directory=tmp_path)
    try:
        with pytest.raises(ArchiveExecutionError) as caught:
            confirm_archive(database, client, archive_chat, ArchiveConfirm(**payload(previous[-1] if previous else None)))
        assert caught.value.progress.round.archive_step == step
        result = retry_archive(database, client, archive_chat, caught.value.progress.round.id, step)
        assert result.round.archive_step == "complete"
    finally:
        client.close()
    logs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(tmp_path.glob("*/metadata.json"))]
    attempts = [record for record in logs if record["purpose"] == step]
    assert [record["attempt"] for record in attempts] == [1, 2]
    assert attempts[0]["result"] == "success"  # HTTP succeeded; content validation failed.
    assert attempts[0]["workflow_result"] == "error" and attempts[0]["workflow_error_type"] == error_type
    assert attempts[1]["workflow_result"] == "success"
