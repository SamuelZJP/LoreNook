"""Local ComfyUI over its HTTP API: queue a workflow, wait in history, download the first image."""

from dataclasses import dataclass
import time
from uuid import uuid4

import httpx

from backend.schemas.models import validate_base_url
from backend.shared.errors import IllustrationError, ModelConfigurationError

MEDIA_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@dataclass(frozen=True)
class RenderedImage:
    data: bytes
    media_type: str


def _short(text: str, limit: int = 500) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _rejection(body) -> str:
    if not isinstance(body, dict):
        return ""
    parts = []
    error = body.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        parts.append(error["message"])
    nodes = body.get("node_errors")
    if isinstance(nodes, dict):
        for node_id, info in nodes.items():
            if not isinstance(info, dict):
                continue
            for item in info.get("errors") or []:
                if isinstance(item, dict):
                    detail = " ".join(str(item[key]) for key in ("message", "details") if item.get(key))
                    parts.append(f"节点 {node_id}（{info.get('class_type', '?')}）：{detail}")
    return _short("；".join(parts))


def _execution_error(status) -> str:
    for message in (status or {}).get("messages") or []:
        if isinstance(message, list) and len(message) == 2 and message[0] == "execution_error":
            info = message[1] if isinstance(message[1], dict) else {}
            node = info.get("node_type") or info.get("node_id") or "?"
            return _short(f"节点 {node}：{info.get('exception_message', '').strip()}")
    return ""


class ComfyUIClient:
    def __init__(self, *, transport: httpx.BaseTransport | None = None, timeout_seconds: float = 600,
                 poll_seconds: float = 1.0, max_image_bytes: int = 64 * 1024 * 1024,
                 sleep=time.sleep, clock=time.monotonic):
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.max_image_bytes = max_image_bytes
        self.sleep, self.clock = sleep, clock
        self.http = httpx.Client(transport=transport, follow_redirects=False, trust_env=False,
                                 timeout=httpx.Timeout(30, connect=10))

    def close(self) -> None:
        self.http.close()

    def render(self, base_url: str, workflow: dict) -> RenderedImage:
        try:
            base = validate_base_url(base_url).rstrip("/")
        except ModelConfigurationError:
            raise IllustrationError("ComfyUI 地址必须是 HTTP(S) 根地址") from None
        try:
            prompt_id = self._queue(base, workflow)
            outputs = self._wait(base, prompt_id)
            return self._download(base, outputs)
        except httpx.TimeoutException:
            raise IllustrationError("ComfyUI 请求超时") from None
        except httpx.HTTPError:
            raise IllustrationError("无法连接 ComfyUI") from None

    @staticmethod
    def _json(response: httpx.Response):
        try:
            return response.json()
        except ValueError:
            return None

    def _queue(self, base: str, workflow: dict) -> str:
        response = self.http.post(f"{base}/prompt", json={"prompt": workflow, "client_id": f"lorenook-{uuid4()}"})
        body = self._json(response)
        if response.status_code == 400:
            raise IllustrationError(f"ComfyUI 拒绝了工作流：{_rejection(body) or '未说明原因'}")
        if not response.is_success:
            raise IllustrationError(f"ComfyUI 返回 HTTP {response.status_code}")
        prompt_id = body.get("prompt_id") if isinstance(body, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise IllustrationError("ComfyUI 没有返回任务 ID")
        return prompt_id

    def _wait(self, base: str, prompt_id: str) -> dict:
        deadline = self.clock() + self.timeout_seconds
        while True:
            response = self.http.get(f"{base}/history/{prompt_id}")
            if not response.is_success:
                raise IllustrationError(f"ComfyUI 返回 HTTP {response.status_code}")
            body = self._json(response)
            entry = body.get(prompt_id) if isinstance(body, dict) else None
            if isinstance(entry, dict):
                status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
                if status.get("status_str") == "error":
                    raise IllustrationError(f"ComfyUI 执行失败：{_execution_error(status) or '未说明原因'}")
                outputs = entry.get("outputs")
                if not isinstance(outputs, dict):
                    raise IllustrationError("ComfyUI 任务记录缺少输出")
                return outputs
            if self.clock() >= deadline:
                raise IllustrationError("ComfyUI 生成超时")
            self.sleep(self.poll_seconds)

    def _download(self, base: str, outputs: dict) -> RenderedImage:
        images = [image for node in outputs.values() if isinstance(node, dict)
                  for image in node.get("images") or [] if isinstance(image, dict) and image.get("filename")]
        if not images:
            raise IllustrationError("工作流没有输出图像，请确认包含 SaveImage 节点")
        image = next((item for item in images if item.get("type") == "output"), images[0])
        params = {"filename": image["filename"], "subfolder": image.get("subfolder", ""),
                  "type": image.get("type", "output")}
        with self.http.stream("GET", f"{base}/view", params=params) as response:
            if not response.is_success:
                raise IllustrationError(f"ComfyUI 返回 HTTP {response.status_code}")
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type not in MEDIA_TYPES:
                raise IllustrationError("ComfyUI 输出不是 PNG、JPEG 或 WebP 图像")
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > self.max_image_bytes:
                    raise IllustrationError("ComfyUI 输出图像过大")
        if not data:
            raise IllustrationError("ComfyUI 输出图像为空")
        return RenderedImage(bytes(data), media_type)
