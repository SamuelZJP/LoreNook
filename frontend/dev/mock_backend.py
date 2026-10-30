"""Run the real LoreNook backend against a separate SQLite file with mocked model calls.

For frontend development and testing only: no network requests reach any model provider.

    python frontend/dev/mock_backend.py [--port 8000] [--db data/mock.db] [--reset] [--no-seed]

Markers in the user input control the mock models (they reach every prompt that includes the input):
    [[fail-writing]]          writing call returns HTTP 500 (every time)
    [[fail-state_update]]     first state-update call fails; retry succeeds
    [[fail-round_summary]]    first round-summary call fails; retry succeeds
    [[fail-episode_summary]]  first episode-summary call fails; retry succeeds
    [[bad-output]]            writing returns text without <content> (preset parse rejects it)
    [[newday]]                state update advances 世界.日期 by one day (drives episode decisions)
    [[slow]]                  each model call for this input waits 15 seconds
    [[fail-image]]            the mock ComfyUI rejects the workflow for this round

Illustrations go to a mock ComfyUI that draws a gradient after a few seconds; images are kept in
data/mock-images and uploads in data/mock-media.
"""

import argparse
import datetime
import json
import os
import random
import re
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

failed_once: set[str] = set()
day_offset = 0
write_count = 0


def text_of(body: dict) -> tuple[str, str]:
    """Return (system text, all other text) for Google or DeepSeek request bodies."""
    if "contents" in body:
        system = "".join(p.get("text", "") for p in body.get("systemInstruction", {}).get("parts", []))
        rest = "".join(p.get("text", "") for c in body["contents"] for p in c.get("parts", []))
        return system, rest
    messages = body.get("messages", [])
    system = "".join(m.get("content", "") for m in messages if m.get("role") == "system")
    rest = "".join(m.get("content", "") for m in messages if m.get("role") != "system")
    return system, rest


def classify(body: dict, system: str) -> str:
    if "插图提示词助手" in system:
        return "image_prompt"
    if "JSON Patch" in system or "JSONPatch" in system:
        return "state_update"
    if "连续回合" in system:
        return "episode_summary"
    if body.get("tools") or "game_content" in json.dumps(body, ensure_ascii=False):
        return "writing"
    if "摘要" in system:
        return "round_summary"
    return "writing"


def google(text: str | None = None, *, call: str | None = None) -> httpx.Response:
    part = {"functionCall": {"name": "game_content", "args": {"content": call}}} if call is not None else {"text": text}
    return httpx.Response(200, json={
        "candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [part]}}],
        "usageMetadata": {"totalTokenCount": 1},
    })


def deepseek(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"index": 0, "finish_reason": "stop",
                                                  "message": {"role": "assistant", "content": text}}]})


def handler(request: httpx.Request) -> httpx.Response:
    global day_offset, write_count
    body = json.loads(request.content)
    system, rest = text_of(body)
    step = classify(body, system)
    is_google = "contents" in body
    everything = system + rest
    if "[[slow]]" in everything:
        time.sleep(15)
    if step == "writing" and "[[fail-writing]]" in everything:
        return httpx.Response(500, json={"error": {"message": "mock failure"}})
    marker = f"[[fail-{step}]]"
    if step != "writing" and marker in everything:
        key = step + str(hash(rest))
        if key not in failed_once:
            failed_once.add(key)
            return httpx.Response(500, json={"error": {"message": "mock failure"}})

    if step == "writing":
        write_count += 1
        if "[[bad-output]]" in everything:
            content = "<report_nya~>没有正文</report_nya~>"
        else:
            content = (f"<report_nya~>模拟报告 #{write_count}</report_nya~>\n"
                       f"<content>（模拟回复 #{write_count}）她点了点头。\n\n“我明白了，**继续吧**。”</content>")
        return google(call=content) if is_google else deepseek(content)
    if step == "image_prompt":
        line = next((l for l in rest.splitlines() if "恰好包含这些字符串字段" in l), "")
        fields = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', line) or ["prompt"]
        values = {name: ("" if "negative" in name else f"mock {name}, 1girl, library, warm light") for name in fields}
        if "[[fail-image]]" in rest:
            values = {name: f"{value} [[fail-image]]" for name, value in values.items()}
        text = json.dumps(values, ensure_ascii=False)
    elif step == "state_update":
        patch = "[]"
        if "[[newday]]" in rest:
            day_offset += 1
            date = (datetime.date(2026, 10, 19) + datetime.timedelta(days=day_offset)).isoformat()
            patch = json.dumps([{"op": "replace", "path": "/世界/日期", "value": date}], ensure_ascii=False)
        text = f"<UpdateVariable><Analysis>模拟结算。</Analysis><JSONPatch>{patch}</JSONPatch></UpdateVariable>"
    elif step == "episode_summary":
        text = json.dumps({"title": "模拟情节", "summary": "2026/10/19-2026/10/20—某地\n这是一段模拟的情节摘要。"},
                          ensure_ascii=False)
    else:
        text = "2026/10/19—08:00—某地\n这是一段模拟的回合摘要。"
    return google(text) if is_google else deepseek(text)


comfy_jobs: dict[str, dict] = {}


def png(width: int, height: int, seed: int) -> bytes:
    """A dusk-like vertical gradient with a soft sun, so plates have something to show."""
    rng = random.Random(seed)
    top = [rng.randint(40, 110) for _ in range(3)]
    bottom = [rng.randint(170, 250) for _ in range(3)]
    sx, sy, sr = rng.uniform(0.2, 0.8) * width, rng.uniform(0.45, 0.7) * height, height * 0.16
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        t = y / max(1, height - 1)
        base = [round(a + (b - a) * t) for a, b in zip(top, bottom)]
        ground = y > height * 0.78
        for x in range(width):
            if ground:
                rows += bytes(round(c * 0.35) for c in base)
                continue
            d = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
            glow = max(0.0, 1 - d / sr) ** 1.5
            rows += bytes(min(255, round(c + (255 - c) * glow)) for c in base)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + chunk(b"IEND", b"")


def comfy_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/upload/image":
        return httpx.Response(200, json={"name": "mock-reference.png", "subfolder": "", "type": "input"})
    if request.method == "POST" and request.url.path == "/prompt":
        workflow = json.loads(request.content)["prompt"]
        if "[[fail-image]]" in json.dumps(workflow, ensure_ascii=False):
            return httpx.Response(400, json={"error": {"message": "Prompt outputs failed validation"},
                                             "node_errors": {"4": {"class_type": "CheckpointLoaderSimple", "errors": [
                                                 {"message": "Value not in list", "details": "ckpt_name: 'mock.safetensors'"}]}}})
        latent = workflow.get("5", {}).get("inputs", {})
        job = f"mock-{len(comfy_jobs) + 1}"
        comfy_jobs[job] = {"at": time.monotonic(), "seed": workflow.get("3", {}).get("inputs", {}).get("seed", 0),
                           "width": latent.get("width", 1344), "height": latent.get("height", 768)}
        return httpx.Response(200, json={"prompt_id": job, "number": 1, "node_errors": {}})
    if request.url.path.startswith("/history/"):
        job = request.url.path.rsplit("/", 1)[1]
        if job not in comfy_jobs or time.monotonic() - comfy_jobs[job]["at"] < 4:
            return httpx.Response(200, json={})
        return httpx.Response(200, json={job: {"status": {"status_str": "success", "completed": True}, "outputs": {
            "9": {"images": [{"filename": f"{job}.png", "subfolder": "", "type": "output"}]}}}})
    if request.url.path == "/view":
        job = comfy_jobs[request.url.params["filename"].removesuffix(".png")]
        scale = 480 / max(job["width"], job["height"])
        data = png(round(job["width"] * scale), round(job["height"] * scale), int(job["seed"]))
        return httpx.Response(200, content=data, headers={"content-type": "image/png"})
    return httpx.Response(404)


MOCK_WORKFLOW = {
    "3": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", "steps": 20, "cfg": 7, "sampler_name": "euler",
                                               "scheduler": "normal", "denoise": 1, "model": ["4", 0],
                                               "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "mock.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{width}}", "height": "{{height}}", "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "masterpiece, {{prompt}}", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "lowres, {{negative_prompt}}", "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "LoreNook", "images": ["8", 0]}},
}


def seed(app) -> None:
    from fastapi.testclient import TestClient

    schema = (ROOT / "backend/modules/state/examples/basic.py").read_text(encoding="utf-8")
    preset = (ROOT / "backend/modules/presets/examples/google_tool.js").read_text(encoding="utf-8")
    with TestClient(app) as client:
        if not client.get("/api/image-workflows").json():
            client.post("/api/image-workflows", json={
                "name": "模拟 SDXL", "base_url": "http://127.0.0.1:8188", "workflow": MOCK_WORKFLOW,
            }).raise_for_status()
            client.post("/api/image-workflows", json={
                "name": "模拟 图生图", "base_url": "http://127.0.0.1:8188", "width": 832, "height": 1216,
                "workflow": {**MOCK_WORKFLOW, "10": {"class_type": "LoadImage", "inputs": {"image": "{{image:focus_1}}"}}},
            }).raise_for_status()
            print("Seeded mock image workflow.")
        if client.get("/api/characters").json():
            return
        client.post("/api/characters", json={
            "name": "示例角色", "description": "用于前端开发的示例角色",
            "scenes": [
                {"name": "图书馆", "description": "早晨，图书馆刚开门",
                 "first_message": "<content>“你来了。”她从书页上抬起头。</content>"},
                {"order": 1, "name": "闭馆后", "description": "夜晚，只剩你们两人",
                 "first_message": "<content>灯一盏盏熄灭，她合上了最后一本书。</content>",
                 "initial_state": {"世界": {"时间": "21:30", "地点": "图书馆"}, "角色": {"好感度": 30, "关系": "熟人"}}},
            ],
            "state_schema": schema,
            "definitions": [{"content": "她是一名图书管理员。"},
                            {"content": "当前时间：{{ state[\"世界\"][\"时间\"] }}", "has_template": True}],
        }).raise_for_status()
        client.post("/api/user-identities", json={"name": "旅人", "description": "示例身份"}).raise_for_status()
        client.post("/api/writing-presets", json={"name": "Google 工具示例", "source": preset}).raise_for_status()
        client.post("/api/model-configs", json={
            "name": "模拟 Google", "api_type": "google_generate_content",
            "base_url": "https://mock.invalid/v1beta", "model": "mock-model", "api_key": "mock-key",
        }).raise_for_status()
        print("Seeded example character, identity, preset and mock model configuration.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default="data/mock.db", help="SQLite path relative to the project root")
    parser.add_argument("--reset", action="store_true", help="delete the mock database first")
    parser.add_argument("--no-seed", action="store_true")
    args = parser.parse_args()

    db_path = (ROOT / args.db).resolve()
    if args.reset and db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path.as_posix()}"
    os.environ["LORENOOK_DATABASE_URL"] = url
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True,
                   env={**os.environ, "LORENOOK_DATABASE_URL": url})

    import uvicorn
    from backend.config import Settings
    from backend.main import create_app

    images, media = str(ROOT / "data" / "mock-images"), str(ROOT / "data" / "mock-media")
    app = create_app(Settings(database_url=url, image_directory=images, media_directory=media, comfyui_poll_seconds=0.5),
                     llm_transport=httpx.MockTransport(handler), comfyui_transport=httpx.MockTransport(comfy_handler))
    if not args.no_seed:
        seed(app)
    print(f"Mock backend on http://127.0.0.1:{args.port} using {db_path}")
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
