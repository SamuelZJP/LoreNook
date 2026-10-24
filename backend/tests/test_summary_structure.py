import json
import sqlite3

import httpx
import pytest

from alembic import command
from backend.llm.generation import text_request
from backend.modules.episode_summary.generate import parse_episode
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Character, Chat, Round
from backend.repository.queries import Repository
from backend.shared.errors import EpisodeSummaryError
from backend.tests.test_catalog_api import run_api
from backend.tests.conftest import migration_config
from backend.tests.test_episode_summary import pending_episode, text_response, TITLE, TEXT
from backend.tests.test_round_summary import summary_round, text_response as round_response


@pytest.mark.parametrize("text", ["not JSON", "[]", "null", "{}", '{"title":"x"}',
    '{"title":"x","summary":" "}', '{"title":" ","summary":"x"}',
    '{"title":3,"summary":"x"}', '{"title":"x","summary":3}',
    '{"title":"x","summary":"x","extra":1}',
    '{"title":"x","title":"y","summary":"x"}',
    json.dumps({"title": "长" * 21, "summary": "内容"}),
    '{"title":"x","summary":"\\ud800"}',
    'prefix {"title":"x","summary":"x"}',
    '{"title":"x","summary":"x"} {"title":"y","summary":"y"}',
])
def test_invalid_episode_json_is_not_a_successful_summary(text):
    with pytest.raises(EpisodeSummaryError):
        parse_episode(text)


@pytest.mark.parametrize("fenced", [False, True])
def test_episode_json_keeps_field_text_and_accepts_single_fence(fenced):
    text = json.dumps({"title": "保留标题", "summary": " 正文\r\n"}, ensure_ascii=False)
    value = parse_episode("```json\n" + text + "\n```" if fenced else text)
    assert value.title == "保留标题" and value.summary == " 正文\r\n"


def test_episode_json_native_response_modes():
    for api, key, expected in [("google_generate_content", "generationConfig", {"candidateCount": 1, "responseMimeType": "application/json"}),
                               ("deepseek_chat_completions", "response_format", {"type": "json_object"})]:
        assert text_request(api, "系统", "JSON任务", json_output=True).body[key] == expected


def test_round_prompt_scene_header_pronouns_and_length(database, summary_round):
    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        for phrase in ("## 上下文", "## 当前状态", "## 待摘要内容", "## 任务", "## 摘要格式",
                       "年月日—时分—地点", "约150字", '主角、"我"、用户角色的名称为身份', "不加以解读"):
            assert phrase in prompt
        return httpx.Response(200, json=round_response())
    async def scenario(client):
        response = await client.post(f"/api/chats/{summary_round['chat_id']}/rounds/{summary_round['round_id']}/round-summary")
        assert response.status_code == 200
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_first_message_episode_title_edit_and_memory(database, pending_episode):
    ids = pending_episode
    with database.transaction() as session:
        repo = Repository(session)
        repo.get(Character, ids["character_id"]).first_message = "<report_nya~>开场报告不提供</report_nya~><content>开场事实{{user}}</content>"
        chat = repo.get(Chat, ids["chat_id"])
        chat.recent_rounds, chat.min_summaries = 0, 0
    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "[首条消息]\n开场事实身份" in prompt and "开场报告不提供" not in prompt
        assert "## 已归档的最后一个对话回合" not in prompt
        assert "约200~300字" in prompt and "不超过20字" in prompt
        assert "起始时间(yyyy/mm/dd)-终止时间(yyyy/mm/dd)—地点" in prompt
        assert "完整用户输入5" in prompt and "完整用户输入6" not in prompt
        return httpx.Response(200, json=text_response())
    async def scenario(client):
        root = f"/api/chats/{ids['chat_id']}"
        response = await client.post(root + f"/rounds/{ids['round_id']}/episode-summary")
        assert response.status_code == 200, response.text
        episode = response.json()["episode"]
        assert episode["title"] == TITLE and episode["summary"] == TEXT
        memory = (await client.get(root + "/memory")).json()
        assert memory["items"][0]["title"] == TITLE
        path = root + "/episodes/" + episode["id"]
        assert (await client.put(path, json={"summary": TEXT, "title": "新标题"})).json()["title"] == "新标题"
        assert (await client.put(path, json={"summary": "新摘要"})).json()["title"] == "新标题"
        assert (await client.put(path, json={"summary": "x", "title": "长" * 21})).status_code == 422
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_malformed_episode_json_keeps_range_and_can_retry(database, pending_episode):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=text_response('{"title":"缺少摘要"}') if len(calls) == 1 else text_response())
    async def scenario(client):
        ids = pending_episode
        path = f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}/episode-summary"
        assert (await client.post(path)).status_code == 422
        progress = (await client.get(f"/api/chats/{ids['chat_id']}/rounds/{ids['round_id']}")).json()
        assert progress["round"]["archive_step"] == "episode_summary" and progress["episode"] is None
        assert progress["round"]["episode_start_round_id"] == ids["ids"][0]
        assert (await client.post(path)).json()["episode"]["title"] == TITLE
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_bridge_is_reference_only_and_change_rejects_stale_generation(database, pending_episode):
    ids = pending_episode
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        repo.save_episode(ids["round_id"], "旧情节", title="旧标题")
        for number in range(7, 12):
            record = repo.create_round(ids["chat_id"], f"用户{number}", f"<content>正文{number}</content>")
            repo.save_state(record.id, {"世界": {"日期": "2026-10-20"}})
            repo.save_summary(record.id, f"摘要{number}")
            if number < 11:
                repo.save_decision(record.id)
        rid = record.id
        repo.save_decision(rid, start_round_id=ids["round_id"], end_round_id=repo.rounds(ids["chat_id"])[9].id)
        repo.get(Character, ids["character_id"]).first_message = "首条消息不应再次提供"
    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        assert "跨事件边界的桥接上下文" in prompt and "[回合5AI] 完整 AI 正文5" in prompt
        assert "首条消息不应再次提供" not in prompt and "旧情节" not in prompt
        assert "[回合4AI]" not in prompt and "正文11" not in prompt
        with database.transaction() as session:
            Repository(session).get(Round, ids["ids"][4]).user_input = "桥接输入已改变"
        return httpx.Response(200, json=text_response())
    async def scenario(client):
        assert (await client.post(f"/api/chats/{ids['chat_id']}/rounds/{rid}/episode-summary")).status_code == 409
    run_api(database, scenario, llm_transport=httpx.MockTransport(handler))


def test_upgrade_existing_episode_preserves_history_and_defaults_title(database, pending_episode, tmp_path):
    with database.transaction() as session:
        ArchiveRepository(session).save_episode(pending_episode["round_id"], " 原历史摘要\r\n", title="旧标题")
    database.dispose()
    config = migration_config(tmp_path / "test.db")
    command.downgrade(config, "bc8b253579a2")
    with sqlite3.connect(tmp_path / "test.db") as connection:
        before = connection.execute("select id,summary,start_round_id,end_round_id,created_by_round_id from episodes").fetchall()
        assert "title" not in [row[1] for row in connection.execute("pragma table_info(episodes)")]
    command.upgrade(config, "head")
    with sqlite3.connect(tmp_path / "test.db") as connection:
        after = connection.execute("select id,summary,start_round_id,end_round_id,created_by_round_id from episodes").fetchall()
        assert before == after and after[0][1] == " 原历史摘要\r\n"
        assert connection.execute("select title from episodes").fetchall() == [("",)]
