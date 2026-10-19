import json

import httpx
import pytest

from backend.llm.client import ModelClient
from backend.shared.errors import ModelCallError, PresetExecutionError
from backend.tests.test_models import BODY, RESULT, connection
from backend.schemas.presets import BuiltRequest
from backend.tests.test_writing import writing_chat, database_contents
from backend.workflows.writing import generate_writing
from backend.tests.test_archive_workflow import archive_chat, seed_history, successful_handler, payload
from backend.workflows.archive import confirm_archive
from backend.schemas.archive import ArchiveConfirm


def metadata(root):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*/metadata.json"))]


def test_exact_final_request_full_reply_and_restart_attempts(tmp_path):
    seen = []
    raw = json.dumps({**RESULT, "other": [1, {"unrecognized": "完整回复"}],
                      "candidates": RESULT["candidates"] * 2}, ensure_ascii=False).encode()

    def handler(request):
        seen.append(request.content)
        return httpx.Response(200, content=raw)

    request = BuiltRequest(api_type="google_generate_content", body={**BODY, "model": "models/override"})
    config = connection(default_parameters={"generationConfig": {"topP": 0.8}})
    for _ in range(2):
        client = ModelClient(transport=httpx.MockTransport(handler), recording_directory=tmp_path)
        try:
            assert client.invoke(config, request).response == json.loads(raw)
        finally:
            client.close()
    rows = metadata(tmp_path)
    assert [r["attempt"] for r in rows] == [1, 2]
    for row, sent in zip(rows, seen):
        assert (tmp_path / row["request_file"]).read_bytes() == sent
        assert "model" not in json.loads(sent)
        assert json.loads(sent)["generationConfig"] == {"topP": 0.8}
        assert (tmp_path / row["response_file"]).read_bytes() == raw
        assert row["model"] == "override" and row["response_complete"]
        assert json.loads((tmp_path / row["response_json_file"]).read_text(encoding="utf-8")) == json.loads(raw)
    assert "private-test-key" not in "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file())
    events = [json.loads(line) for line in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[0]["result"] == "started" and events[-1]["result"] == "success"


@pytest.mark.parametrize("case,kind", [("http", "http"), ("invalid", "invalid_response"),
                                        ("provider", "provider"), ("large", "response_too_large"),
                                        ("timeout", "timeout"), ("network", "network")])
def test_complete_failure_replies_and_safe_errors(tmp_path, case, kind):
    raw = {"http": b'{"error":"full http failure"}', "invalid": b"not json\r\n",
           "provider": b'{"error":{"details":[1,2,3]}}', "large": b'{"x":"' + b"x" * 1000 + b'"}'}

    def handler(request):
        if case in {"timeout", "network"}:
            raise (httpx.ReadTimeout if case == "timeout" else httpx.ReadError)("private-test-key", request=request)
        return httpx.Response(429 if case == "http" else 200, content=raw[case])

    client = ModelClient(transport=httpx.MockTransport(handler), recording_directory=tmp_path,
                         max_response_bytes=100 if case == "large" else 10000)
    try:
        with pytest.raises(ModelCallError) as error:
            client.invoke(connection(), BuiltRequest(api_type="google_generate_content", body=BODY))
        assert error.value.kind == kind
    finally:
        client.close()
    row = metadata(tmp_path)[0]
    assert row["result"] == kind
    assert row["response_complete"] == (case not in {"timeout", "network"})
    assert (tmp_path / row["response_file"]).read_bytes() == raw.get(case, b"")
    assert "private-test-key" not in json.dumps(row)


def test_partial_response_survives_timeout(tmp_path):
    class Partial(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"partial":'
            raise httpx.ReadTimeout("private-test-key")
    client = ModelClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=Partial())),
                         recording_directory=tmp_path)
    try:
        with pytest.raises(ModelCallError):
            client.invoke(connection(), BuiltRequest(api_type="google_generate_content", body=BODY))
    finally:
        client.close()
    row = metadata(tmp_path)[0]
    assert row["result"] == "timeout" and not row["response_complete"]
    assert (tmp_path / row["response_file"]).read_bytes() == b'{"partial":'


def test_writing_parse_failure_records_full_upstream_without_saving(database, writing_chat, tmp_path):
    before = database_contents(database)
    raw = {"unexpected": "完整响应", **RESULT}
    client = ModelClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=raw)),
                         recording_directory=tmp_path)
    try:
        for _ in range(2):
            with pytest.raises(PresetExecutionError):
                generate_writing(database, client, writing_chat["chat_id"], " 用户输入\n")
    finally:
        client.close()
    assert database_contents(database) == before
    rows = metadata(tmp_path)
    assert [r["attempt"] for r in rows] == [1, 2]
    for row in rows:
        assert row["chat_id"] == writing_chat["chat_id"] and row["round_no"] == 1
        assert row["purpose"] == "writing" and row["workflow_result"] == "error"
        assert row["workflow_error_type"] == "PresetExecutionError" and row["result"] == "success"
        assert json.loads((tmp_path / row["response_file"]).read_bytes()) == raw


def test_archive_records_all_purposes_and_persisted_round(database, archive_chat, tmp_path):
    previous = seed_history(database, archive_chat)
    calls = []
    client = ModelClient(transport=httpx.MockTransport(successful_handler(calls, new_day=True)),
                         recording_directory=tmp_path)
    try:
        progress = confirm_archive(database, client, archive_chat, ArchiveConfirm(**payload(previous[-1])))
    finally:
        client.close()
    assert progress.round.archive_step == "complete"
    rows = metadata(tmp_path)
    assert [r["purpose"] for r in rows] == ["state_update", "round_summary", "episode_summary"]
    assert len(calls) == len(rows) == 3
    for row in rows:
        assert row["chat_id"] == archive_chat and row["round_id"] == progress.round.id
        assert row["round_no"] == 6 and row["attempt"] == 1
        assert row["workflow_result"] == "success" and row["response_complete"]
