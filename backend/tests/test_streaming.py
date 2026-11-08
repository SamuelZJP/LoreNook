import json

import httpx
import pytest

from backend.llm.client import ModelClient
from backend.llm.generation import response_text, text_request
from backend.llm.sse import sse_events
from backend.schemas.presets import BuiltRequest
from backend.shared.errors import ModelCallError
from backend.tests.test_models import connection

DEEPSEEK = "deepseek_chat_completions"
GOOGLE = "google_generate_content"
SSE = {"content-type": "text/event-stream"}


def sse(*events, done=True):
    lines = [f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events]
    return ("".join(lines) + ("data: [DONE]\n\n" if done else "")).encode()


def invoke(api_type, handler, body, tmp_path=None, **config):
    client = ModelClient(transport=httpx.MockTransport(handler), recording_directory=tmp_path)
    try:
        return client.invoke(connection(**{"api_type": api_type, "streaming": True, **config}),
                             BuiltRequest(api_type=api_type, body=body)).response
    finally:
        client.close()


def chunk(delta, finish=None, index=0):
    return {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "m",
            "choices": [{"index": index, "delta": delta, "finish_reason": finish}]}


DEEPSEEK_EVENTS = [
    chunk({"role": "assistant", "content": "", "reasoning_content": "想"}),
    chunk({"reasoning_content": "一想"}),
    chunk({"content": " 正文"}),
    chunk({"content": "\r\n", "tool_calls": [{"index": 0, "id": "t1", "type": "function",
                                              "function": {"name": "f", "arguments": "{\"a\""}}]}),
    chunk({"tool_calls": [{"index": 0, "function": {"arguments": ": 1}"}}]}),
    chunk({}, "stop"),
    {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "m", "choices": [],
     "usage": {"total_tokens": 9}},
]


def test_deepseek_stream_request_and_joined_response(tmp_path):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        assert str(request.url) == "https://provider.test/v1beta/chat/completions"
        return httpx.Response(200, headers=SSE, content=sse(*DEEPSEEK_EVENTS))
    result = invoke(DEEPSEEK, handler, {"messages": [{"role": "user", "content": "x"}], "stream": False,
                                        "stream_options": {"other": 1}}, tmp_path)
    assert seen[0]["stream"] is True and seen[0]["stream_options"] == {"other": 1, "include_usage": True}
    assert result == {"object": "chat.completion", "id": "c1", "created": 1, "model": "m",
                      "usage": {"total_tokens": 9}, "choices": [{
                          "index": 0, "finish_reason": "stop", "logprobs": None, "message": {
                              "role": "assistant", "content": " 正文\r\n", "reasoning_content": "想一想",
                              "tool_calls": [{"id": "t1", "type": "function",
                                              "function": {"name": "f", "arguments": "{\"a\": 1}"}}]}}]}
    meta = json.loads((tmp_path / "000001/metadata.json").read_text(encoding="utf-8"))
    assert meta["streaming"] is True and meta["response_complete"] is True
    assert (tmp_path / "000001/response.raw").read_bytes() == sse(*DEEPSEEK_EVENTS)


def test_streamed_text_matches_non_streaming_parsing():
    events = [chunk({"role": "assistant", "content": "你"}), chunk({"content": "好"}, "stop")]
    result = invoke(DEEPSEEK, lambda r: httpx.Response(200, headers=SSE, content=sse(*events)),
                    text_request(DEEPSEEK, "系统", "用户").body)
    assert response_text(DEEPSEEK, result) == "你好"


def test_non_streaming_config_sends_stream_false():
    def handler(request):
        body = json.loads(request.content)
        assert body["stream"] is False and "stream_options" not in body
        return httpx.Response(200, json={"choices": []})
    invoke(DEEPSEEK, handler, {"messages": [{}], "stream": True, "stream_options": {}}, streaming=False)


GOOGLE_EVENTS = [
    {"candidates": [{"content": {"role": "model", "parts": [{"text": "思", "thought": True}]}, "index": 0}]},
    {"candidates": [{"content": {"role": "model", "parts": [{"text": "考", "thought": True}]}, "index": 0}]},
    {"candidates": [{"content": {"role": "model", "parts": [{"text": " 正"}]}, "index": 0}]},
    {"candidates": [{"content": {"role": "model", "parts": [{"text": "文", "thoughtSignature": "sig"}]},
                     "index": 0}]},
    {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": "f", "args": {}}}]},
                     "finishReason": "STOP", "index": 0}],
     "usageMetadata": {"totalTokenCount": 5}, "modelVersion": "v"},
]


def test_google_stream_endpoint_and_joined_response():
    def handler(request):
        assert str(request.url) == "https://provider.test/v1beta/models/example-model:streamGenerateContent?alt=sse"
        return httpx.Response(200, headers=SSE, content=sse(*GOOGLE_EVENTS, done=False))
    result = invoke(GOOGLE, handler, {"contents": [{"role": "user", "parts": [{"text": "x"}]}]})
    assert result == {"usageMetadata": {"totalTokenCount": 5}, "modelVersion": "v", "candidates": [{
        "index": 0, "finishReason": "STOP", "content": {"role": "model", "parts": [
            {"text": "思考", "thought": True}, {"text": " 正文", "thoughtSignature": "sig"},
            {"functionCall": {"name": "f", "args": {}}}]}}]}


def test_google_blocked_prompt_passes_through():
    event = {"promptFeedback": {"blockReason": "SAFETY"}}
    result = invoke(GOOGLE, lambda r: httpx.Response(200, headers=SSE, content=sse(event, done=False)),
                    {"contents": [{}]})
    assert result == event


@pytest.mark.parametrize("api_type,content,kind", [
    (DEEPSEEK, sse(chunk({"content": "半"})), "invalid_response"),
    (DEEPSEEK, b"", "invalid_response"),
    (DEEPSEEK, b"data: {broken\n\n", "invalid_response"),
    (DEEPSEEK, b"data: [1]\n\n", "invalid_response"),
    (DEEPSEEK, sse(chunk({"content": "x"}), {"error": {"message": "overloaded"}}), "provider"),
    (GOOGLE, sse(GOOGLE_EVENTS[0], done=False), "invalid_response"),
])
def test_broken_streams_fail(api_type, content, kind):
    body = {"messages": [{}]} if api_type == DEEPSEEK else {"contents": [{}]}
    with pytest.raises(ModelCallError) as error:
        invoke(api_type, lambda r: httpx.Response(200, headers=SSE, content=content), body)
    assert error.value.kind == kind


def test_json_answer_to_streaming_request_is_read_as_json():
    with pytest.raises(ModelCallError) as error:
        invoke(DEEPSEEK, lambda r: httpx.Response(200, json={"error": {"message": "no"}}), {"messages": [{}]})
    assert error.value.kind == "provider"
    with pytest.raises(ModelCallError) as error:
        invoke(DEEPSEEK, lambda r: httpx.Response(504, headers=SSE, content=b"gateway"), {"messages": [{}]})
    assert error.value.kind == "http" and error.value.upstream_status == 504


def test_sse_decoding_details():
    raw = b": keepalive\r\nevent: message\r\ndata: {\"a\":\r\ndata: 1}\r\n\r\ndata:{\"b\":\"\xe2\x80\xa8\"}"
    assert sse_events(raw) == [{"a": 1}, {"b": " "}]
