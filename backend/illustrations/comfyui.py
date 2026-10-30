"""Local ComfyUI: upload inputs, queue a workflow, wait in history, download the first image.

While waiting, its WebSocket reports live progress. That only informs the UI: the outcome always
comes from /history, so a socket that won't open or drops costs the progress display and nothing else.
"""

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
import time
from uuid import uuid4

import httpx
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect as websocket_connect

from backend.illustrations.errors import IllustrationError
from backend.schemas.models import validate_base_url
from backend.shared.errors import ModelConfigurationError

logger = logging.getLogger(__name__)

MEDIA_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_SOCKET_MESSAGE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class RenderedImage:
    data: bytes
    media_type: str


@dataclass(frozen=True)
class RenderProgress:
    """Empty means nothing is known, e.g. without a socket."""
    queued: bool = False
    node: str | None = None
    value: int | None = None
    max: int | None = None


ProgressReport = Callable[[RenderProgress], None]


def _connect(url: str):
    return websocket_connect(url, legacy=True, proxy=None, open_timeout=5, close_timeout=1,
                             max_size=MAX_SOCKET_MESSAGE_BYTES)


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
        if isinstance(message, list) and message and message[0] == "execution_interrupted":
            return "任务在 ComfyUI 中被中断"
    return ""


def _node_title(workflow: dict, node_id) -> str | None:
    node = workflow.get(node_id) if isinstance(node_id, str) else None
    if not isinstance(node, dict):
        return None
    meta = node.get("_meta")
    title = meta.get("title") if isinstance(meta, dict) else None
    return title if isinstance(title, str) and title else node.get("class_type")


class _ProgressWatch:
    """Waits between history checks; reads the socket meanwhile, if there is one."""

    def __init__(self, socket, workflow: dict, report: ProgressReport, sleep, clock):
        self.socket, self.workflow, self.report, self.sleep, self.clock = socket, workflow, report, sleep, clock
        self.prompt_id: str | None = None

    def queued(self, prompt_id: str) -> None:
        self.prompt_id = prompt_id
        if self.socket is not None:
            self.report(RenderProgress(queued=True))

    def pause(self, seconds: float) -> None:
        if self.socket is None:
            self.sleep(seconds)
            return
        deadline = self.clock() + seconds
        while (remaining := deadline - self.clock()) > 0:
            try:
                message = self.socket.recv(timeout=remaining)
            except TimeoutError:
                return
            except (OSError, WebSocketException) as error:
                logger.warning("ComfyUI progress socket lost: %s", error)
                self.close()
                self.report(RenderProgress())
                return
            self._handle(message)

    def _handle(self, message) -> None:
        if isinstance(message, bytes):  # A preview frame.
            return
        try:
            parsed = json.loads(message)
        except ValueError:
            return
        data = parsed.get("data") if isinstance(parsed, dict) else None
        if not isinstance(data, dict) or data.get("prompt_id") != self.prompt_id:
            return
        kind = parsed.get("type")
        if kind == "execution_start":
            self.report(RenderProgress())
        elif kind == "executing" and data.get("node") is not None:
            self.report(RenderProgress(node=_node_title(self.workflow, data["node"])))
        elif kind == "progress" and isinstance(data.get("value"), int) and isinstance(data.get("max"), int):
            self.report(RenderProgress(node=_node_title(self.workflow, data.get("node")),
                                       value=data["value"], max=data["max"]))

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None


class ComfyUIClient:
    def __init__(self, *, transport: httpx.BaseTransport | None = None, timeout_seconds: float = 600,
                 poll_seconds: float = 1.0, max_image_bytes: int = 64 * 1024 * 1024,
                 sleep=time.sleep, clock=time.monotonic, connect=None):
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.max_image_bytes = max_image_bytes
        self.sleep, self.clock = sleep, clock
        # An injected transport has no real server behind it, so no socket either unless one is given.
        self.connect = connect or (None if transport else _connect)
        self.http = httpx.Client(transport=transport, follow_redirects=False, trust_env=False,
                                 timeout=httpx.Timeout(30, connect=10))

    def close(self) -> None:
        self.http.close()

    @staticmethod
    def _base(base_url: str) -> str:
        try:
            return validate_base_url(base_url).rstrip("/")
        except ModelConfigurationError:
            raise IllustrationError("ComfyUI 地址必须是 HTTP(S) 根地址") from None

    def upload_image(self, base_url: str, name: str, data: bytes, media_type: str) -> str:
        """Returns the value a LoadImage node expects. Same name, same bytes: overwriting is harmless."""
        try:
            response = self.http.post(f"{self._base(base_url)}/upload/image", data={"overwrite": "true"},
                                      files={"image": (name, data, media_type)})
        except httpx.TimeoutException:
            raise IllustrationError("ComfyUI 请求超时") from None
        except httpx.HTTPError:
            raise IllustrationError("无法连接 ComfyUI") from None
        if not response.is_success:
            raise IllustrationError(f"ComfyUI 上传参考图失败：HTTP {response.status_code}")
        body = self._json(response)
        uploaded = body.get("name") if isinstance(body, dict) else None
        if not isinstance(uploaded, str) or not uploaded:
            raise IllustrationError("ComfyUI 上传参考图后没有返回文件名")
        subfolder = body.get("subfolder")
        return f"{subfolder}/{uploaded}" if subfolder else uploaded

    def render(self, base_url: str, workflow: dict, report: ProgressReport = lambda _: None) -> RenderedImage:
        base = self._base(base_url)
        client_id = f"lorenook-{uuid4()}"
        # Opened before queueing, or the first events would be missed.
        watch = _ProgressWatch(self._socket(base, client_id), workflow, report, self.sleep, self.clock)
        try:
            prompt_id = self._queue(base, workflow, client_id)
            watch.queued(prompt_id)
            outputs = self._wait(base, prompt_id, watch)
            return self._download(base, outputs)
        except httpx.TimeoutException:
            raise IllustrationError("ComfyUI 请求超时") from None
        except httpx.HTTPError:
            raise IllustrationError("无法连接 ComfyUI") from None
        finally:
            watch.close()

    def _socket(self, base: str, client_id: str):
        if self.connect is None:
            return None
        try:
            return self.connect(f"ws{base.removeprefix('http')}/ws?clientId={client_id}")
        except (OSError, WebSocketException) as error:
            logger.warning("ComfyUI progress socket unavailable: %s", error)
            return None

    @staticmethod
    def _json(response: httpx.Response):
        try:
            return response.json()
        except ValueError:
            return None

    def _queue(self, base: str, workflow: dict, client_id: str) -> str:
        response = self.http.post(f"{base}/prompt", json={"prompt": workflow, "client_id": client_id})
        body = self._json(response)
        if response.status_code == 400:
            raise IllustrationError(f"ComfyUI 拒绝了工作流：{_rejection(body) or '未说明原因'}")
        if not response.is_success:
            raise IllustrationError(f"ComfyUI 返回 HTTP {response.status_code}")
        prompt_id = body.get("prompt_id") if isinstance(body, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise IllustrationError("ComfyUI 没有返回任务 ID")
        return prompt_id

    def _wait(self, base: str, prompt_id: str, watch: _ProgressWatch) -> dict:
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
            watch.pause(self.poll_seconds)

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
