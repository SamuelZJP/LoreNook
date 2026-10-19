"""One isolated QuickJS context per synchronous transform; no host callbacks."""

import json

import quickjs
from pydantic import ValidationError

from backend.schemas.presets import BuiltRequest, ParsedOutput, WritingMaterials
from backend.shared.errors import PresetExecutionError


def _check_integers(value) -> None:
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
        raise ValueError("整数超出 JavaScript 安全整数范围，请使用字符串表达")
    if isinstance(value, dict):
        for item in value.values():
            _check_integers(item)
    elif isinstance(value, list):
        for item in value:
            _check_integers(item)


class PresetRuntime:
    def __init__(self, *, time_limit: float = 0.5, memory_limit: int = 32 * 1024 * 1024,
                 max_text: int = 2_000_000):
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.max_text = max_text

    def _execute(self, source: str, stage: str, payload: dict):
        try:
            _check_integers(payload)
            argument = json.dumps(payload, ensure_ascii=True, allow_nan=False)
            if len(source) > self.max_text or len(argument) > self.max_text:
                raise ValueError("预设源码或输入超过长度限制")
            context = quickjs.Context()
            context.set_memory_limit(self.memory_limit)
            context.set_max_stack_size(512 * 1024)
            context.set_time_limit(self.time_limit)
            # Capture serialization functions before user code runs. Both entry points
            # must exist; neither closures nor global state survive the next call.
            script = """(() => {
                'use strict';
                const encode = JSON.stringify.bind(JSON);
                const decode = JSON.parse.bind(JSON);
                const finite = Number.isFinite;
                const integer = Number.isInteger;
                const safeInteger = Number.isSafeInteger;
                const entries = (() => {
            """ + source + """
                    if (typeof build !== 'function' || typeof parse !== 'function')
                        throw new Error('预设必须定义 build(materials) 和 parse(response)');
                    return {build, parse};
                })();
                return function (argument) {
                    const value = entries[""" + json.dumps(stage) + """](decode(argument));
                    if (value && typeof value.then === 'function')
                        throw new Error('预设入口必须同步返回，不支持 Promise');
                    const result = encode(value, function (key, item) {
                        if (typeof item === 'number' && !finite(item))
                            throw new Error('结果包含非有限数值');
                        if (typeof item === 'number' && integer(item) && !safeInteger(item))
                            throw new Error('结果整数超出 JavaScript 安全整数范围');
                        if (['undefined', 'function', 'symbol', 'bigint'].includes(typeof item))
                            throw new Error('结果必须只包含 JSON 值');
                        return item;
                    });
                    if (typeof result !== 'string' || result.length > """ + str(self.max_text) + """)
                        throw new Error('结果为空或超过长度限制');
                    return result;
                };
            })()"""
            transform = context.eval(script)
            return json.loads(transform(argument))
        except (quickjs.JSException, ValueError, TypeError, MemoryError, RecursionError) as error:
            raise PresetExecutionError(stage, str(error)[:2000] or "预设执行失败") from error

    def build(self, source: str, materials: WritingMaterials) -> BuiltRequest:
        result = self._execute(source, "build", materials.model_dump())
        try:
            return BuiltRequest.model_validate(result)
        except ValidationError as error:
            raise PresetExecutionError("build", "build 必须返回 {api_type: 非空字符串, body: JSON对象}") from error

    def parse(self, source: str, response: dict) -> ParsedOutput:
        result = self._execute(source, "parse", response)
        try:
            return ParsedOutput(ai_output=result)
        except ValidationError as error:
            raise PresetExecutionError("parse", "parse 必须返回非空白 AI 输出字符串") from error
