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
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
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
    if step == "state_update":
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
        text = "2026-10-19 08:00 某地\n这是一段模拟的回合摘要。"
    return google(text) if is_google else deepseek(text)


def seed(app) -> None:
    from fastapi.testclient import TestClient

    schema = (ROOT / "backend/modules/state/examples/basic.py").read_text(encoding="utf-8")
    preset = (ROOT / "backend/modules/presets/examples/google_tool.js").read_text(encoding="utf-8")
    with TestClient(app) as client:
        if client.get("/api/characters").json():
            return
        client.post("/api/characters", json={
            "name": "示例角色", "description": "用于前端开发的示例角色",
            "first_message": "<content>“你来了。”她从书页上抬起头。</content>", "state_schema": schema,
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

    app = create_app(Settings(database_url=url), llm_transport=httpx.MockTransport(handler))
    if not args.no_seed:
        seed(app)
    print(f"Mock backend on http://127.0.0.1:{args.port} using {db_path}")
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
