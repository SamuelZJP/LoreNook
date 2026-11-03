"""Single synchronous JSON model call, with injectable HTTP transport for tests."""

import json

import httpx

from backend.llm.google import GoogleGenerateContent
from backend.llm.deepseek import DeepSeekChatCompletions
from backend.llm.parameters import merge_parameters
from backend.llm.recording import CallJournal
from backend.schemas.models import ModelConnection, ModelResponse
from backend.schemas.presets import BuiltRequest
from backend.shared.errors import ModelCallError, ModelConfigurationError


def _invalid_constant(value):
    raise ValueError("Response contains a non-JSON number")


class ModelClient:
    def __init__(self, *, transport: httpx.BaseTransport | None = None,
                 max_response_bytes: int = 8 * 1024 * 1024,
                 recording_directory=None):
        self.journal = CallJournal(recording_directory) if recording_directory else None
        self.adapters = {adapter.api_type: adapter for adapter in (GoogleGenerateContent(), DeepSeekChatCompletions())}
        self.max_response_bytes = max_response_bytes
        self.http = httpx.Client(
            transport=transport, follow_redirects=False, trust_env=False,
        )

    def close(self) -> None:
        self.http.close()

    def invoke(self, config: ModelConnection, request: BuiltRequest) -> ModelResponse:
        if config.api_type != request.api_type:
            raise ModelConfigurationError("预设目标接口与模型配置的 api_type 不一致")
        adapter = self.adapters.get(config.api_type)
        if adapter is None:
            raise ModelConfigurationError("当前不支持该 api_type")
        try:
            body = merge_parameters(config.default_parameters, request.body)
            url, headers, body = adapter.prepare(config, body)
            headers["content-type"] = "application/json"
            content = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, RecursionError) as error:
            if isinstance(error, ModelConfigurationError):
                raise
            raise ModelConfigurationError("模型请求参数必须是有效 JSON") from None
        attempt = self.journal.begin(content, api_type=config.api_type,
                                     model=body.get("model", url.rsplit("/", 1)[-1].split(":", 1)[0])) if self.journal else None
        try:
            result = self._send(url, headers, content, attempt, config.timeout_seconds)
        except BaseException as error:
            if attempt:
                attempt.finish(error)
            raise
        if attempt:
            attempt.finish()
        return result

    def _send(self, url, headers, content, attempt, timeout_seconds):
        timeout = httpx.Timeout(timeout_seconds, connect=10, write=30, pool=5)
        try:
            with self.http.stream("POST", url, headers=headers, content=content, timeout=timeout) as response:
                if attempt:
                    attempt.metadata["upstream_status"] = response.status_code
                    attempt.save()
                if not attempt and not 200 <= response.status_code < 300:
                    raise ModelCallError("http", "模型接口返回非成功状态", response.status_code)
                raw = bytearray()
                oversized = False
                for chunk in response.iter_bytes(chunk_size=None if attempt else 65536):
                    if attempt:
                        attempt.chunk(chunk)
                    if len(raw) + len(chunk) > self.max_response_bytes:
                        oversized = True
                        if not attempt:
                            raise ModelCallError("response_too_large", "模型响应超过长度限制")
                    if not oversized:
                        raw.extend(chunk)
                if attempt:
                    attempt.metadata["response_complete"] = True
                if not 200 <= response.status_code < 300:
                    raise ModelCallError("http", "模型接口返回非成功状态", response.status_code)
                if oversized:
                    raise ModelCallError("response_too_large", "模型响应超过长度限制")
            try:
                result = json.loads(raw, parse_constant=_invalid_constant)
                if not isinstance(result, dict):
                    raise ValueError
                json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
                parsed = ModelResponse(response=result)
            except (ValueError, UnicodeError, RecursionError):
                raise ModelCallError("invalid_response", "模型响应必须是有效 JSON 对象") from None
            if "error" in result:
                raise ModelCallError("provider", "模型接口返回错误对象")
            return parsed
        except httpx.TimeoutException:
            raise ModelCallError("timeout", "模型请求超时") from None
        except httpx.HTTPError:
            raise ModelCallError("network", "模型请求连接或传输失败") from None
        except httpx.InvalidURL:
            raise ModelConfigurationError("模型请求地址不合法") from None
