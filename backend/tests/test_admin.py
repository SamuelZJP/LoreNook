from backend.tests.state_fixtures import WORLD
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

from backend.modules.admin.service import AdminService
from backend.repository.admin import AdminRepository, TABLES
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Character, CharacterScene, ChatModelBinding, ModelConfig
from backend.repository.queries import Repository
from backend.schemas.admin import AdminBatch
from backend.shared.errors import ConflictError
from backend.tests.test_catalog_api import run_api
from backend.tests.test_writing import database_contents


@pytest.fixture
def managed_history(database, chat):
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        ids, state_ids = [], []
        for number in range(1, 8):
            record = repo.create_round(chat[0], f"用户原文{number}\r\n", f"<content>正文{number}</content>\n")
            ids.append(record.id)
            state_ids.append(repo.save_state(record.id, {"世界": dict(WORLD), "编号": number}).id)
            repo.save_summary(record.id, f"回合摘要{number}\r\n")
            if number == 6:
                repo.save_decision(record.id, start_round_id=ids[0], end_round_id=ids[4])
                episode_id = repo.save_episode(record.id, "情节原文\r\n").id
            else:
                repo.save_decision(record.id)
        model = repo.add(ModelConfig(chat_id=chat[0], name="模型", api_type="google_generate_content",
                                    base_url="https://provider.test/v1beta", api_key="admin-private-key", model="test"))
        repo.add(ChatModelBinding(chat_id=chat[0], purpose="writing", model_config_id=model.id))
        source = repo.add(Character(name="来源角色"))
        repo.add(CharacterScene(character_id=source.id, name="默认"))
        return {"chat_id": chat[0], "character_id": chat[1], "rounds": ids, "states": state_ids,
                "episode": episode_id, "model": model.id, "source": source.id}


def edit(table, rid, **values):
    return {"action": "update", "table": table, "key": {"id": rid}, "values": values}


def remove(table, rid):
    return {"action": "delete", "table": table, "key": {"id": rid}}


def create(table, **values):
    return {"action": "create", "table": table, "values": values}


async def apply(client, operations, revision=None):
    revision = revision or (await client.get("/api/admin/data")).json()["revision"]
    return await client.post("/api/admin/data", json={"expected_revision": revision, "operations": operations})


def test_schema_and_full_snapshot_are_read_only_and_secrets_are_explicit(database, managed_history):
    before, calls = database_contents(database), []
    async def scenario(client):
        schema = (await client.get("/api/admin/schema")).json()
        assert {entry["name"] for entry in schema} == set(TABLES)
        assert len(schema) == 17
        bindings = next(entry for entry in schema if entry["name"] == "chat_model_bindings")
        assert bindings["primary_key"] == ["chat_id", "purpose"]
        assert "api_key" in next(entry for entry in schema if entry["name"] == "model_configs")["row_schema"]["properties"]
        masked = await client.get("/api/admin/data")
        assert masked.status_code == 200 and "admin-private-key" not in masked.text
        model = masked.json()["tables"]["model_configs"][0]
        assert model["has_api_key"] is True and "api_key" not in model
        full = (await client.get("/api/admin/data?include_secrets=true")).json()
        assert full["revision"] == masked.json()["revision"]
        assert full["tables"]["model_configs"][0]["api_key"] == "admin-private-key"
        assert "has_api_key" not in full["tables"]["model_configs"][0]
        assert "alembic_version" not in full["tables"]
        assert set(full["tables"]) == set(TABLES)
        for name, rows in full["tables"].items():
            assert len(rows) == len(before[name])
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert calls == [] and database_contents(database) == before


def test_create_complete_graph_in_one_batch_with_forward_references(database):
    operations = [
        create("episodes", id="episode", chat_id="chat", start_round_id="r1", end_round_id="r1",
               created_by_round_id="r2", summary=" 情节\r\n"),
        create("state_snapshots", id="s0", chat_id="chat", character_id="character", content={"世界": WORLD}),
        create("state_snapshots", id="s1", chat_id="chat", character_id="character", round_id="r1", content={"世界": WORLD, "值": 1}),
        create("state_snapshots", id="s2", chat_id="chat", character_id="character", round_id="r2", content={"世界": WORLD, "值": True}),
        create("rounds", id="r2", chat_id="chat", round_no=2, user_input="", ai_output="原文二",
               summary="摘要二", archive_step="complete", episode_required=True,
               episode_start_round_id="r1", episode_end_round_id="r1"),
        create("rounds", id="r1", chat_id="chat", round_no=1, user_input="用户原文\r\n", ai_output="原文一",
               summary="摘要一", archive_step="complete", episode_required=False),
        create("definitions", id="definition", character_id="character", content="{{ broken", has_template=True),
        create("chat_model_bindings", chat_id="chat", purpose="writing", model_config_id="model"),
        create("model_configs", id="model", chat_id="chat", name="模型", api_type="自由接口",
               base_url="待配置", api_key="explicit-secret", model="模型名", default_parameters={"a": [1, True, None]}),
        create("writing_presets", id="preset", chat_id="chat", name="预设", source="broken("),
        create("image_workflows", id="workflow", chat_id="chat", name="工作流", base_url="待配置", workflow={"未校验": 1}),
        create("chat_illustration_settings", chat_id="chat", mode="manual", image_workflow_id="workflow",
               model_config_id="model"),
        create("chat_recall_settings", chat_id="chat", model_config_id="model", depth=4),
        create("illustrations", id="illustration", chat_id="chat", round_id="r1", status="failed", seed=7,
               error="失败", width=1344, height=768),
        create("cast_members", id="member", character_id="character", name="人物"),
        create("identity_appearances", user_identity_id="identity", appearance="外貌"),
        create("characters", id="character", chat_id="chat", name="角色", state_schema="broken schema"),
        create("character_scenes", id="scene", character_id="character", name="开场", initial_state={"未校验": True}),
        create("user_identities", id="identity", chat_id="chat", name="身份"),
        create("chats", id="chat", title="完整聊天", writing_preset_id="preset", created_at="2026-10-19T08:00:00+08:00"),
    ]
    async def scenario(client):
        result = await apply(client, operations)
        assert result.status_code == 200, result.text
        assert "explicit-secret" not in result.text
        assert len(result.json()["changes"]) == len(operations)
        snapshot = (await client.get("/api/admin/data")).json()
        assert snapshot["revision"] == result.json()["revision"]
        assert all(snapshot["tables"][name] for name in TABLES)
        assert snapshot["tables"]["chats"][0]["created_at"].startswith("2026-10-19T00:00:00")
        progress = (await client.get("/api/chats/chat/archive")).json()
        assert progress["round"]["id"] == "r2" and progress["state"]["content"] == {"世界": WORLD, "值": True}
        assert progress["episode"]["summary"] == " 情节\r\n"
        memory = await client.get("/api/chats/chat/memory")
        assert memory.status_code == 200
        # The deferred-reference setting must not leak into later transactions.
        invalid = await apply(client, [create("writing_presets", name="悬空预设", chat_id="absent", source="")])
        assert invalid.status_code == 409
        assert (await client.get("/api/admin/data")).json() == snapshot
    run_api(database, scenario)


def test_edit_historical_raw_data_without_schema_or_recalculation(database, managed_history):
    ids, before, calls = managed_history, database_contents(database), []
    async def scenario(client):
        normal = f"/api/chats/{ids['chat_id']}/rounds/{ids['rounds'][0]}/summary"
        assert (await client.put(normal, json={"summary": "历史修改"})).status_code == 409
        result = await apply(client, [
            edit("characters", ids["character_id"], state_schema="无法执行的 Schema"),
            edit("rounds", ids["rounds"][0], user_input=" 新原文\r\n", ai_output="任意原文无标签", summary=" 新摘要\r\n"),
            edit("state_snapshots", ids["states"][0], content={"世界": WORLD, "自由": [True, 1, "字符串", None]}),
        ])
        assert result.status_code == 200, result.text
    run_api(database, scenario, llm_transport=httpx.MockTransport(lambda request: calls.append(request)))
    after = database_contents(database)
    assert calls == []
    assert after["episodes"] == before["episodes"]
    for old, new in zip(before["rounds"], after["rounds"]):
        if old["id"] != ids["rounds"][0]:
            assert old == new
        else:
            assert new["archive_step"] == old["archive_step"] == "complete"
            assert new["ai_output"] == "任意原文无标签" and new["summary"] == " 新摘要\r\n"
    with database.read() as session:
        assert Repository(session).state_for_round(ids["chat_id"], ids["rounds"][0]).content == {"世界": WORLD, "自由": [True, 1, "字符串", None]}


def test_range_and_producer_must_be_edited_together(database, managed_history):
    ids = managed_history
    async def scenario(client):
        before = (await client.get("/api/admin/data")).json()
        one = edit("episodes", ids["episode"], end_round_id=ids["rounds"][3])
        assert (await apply(client, [one])).status_code == 409
        assert (await client.get("/api/admin/data")).json() == before
        result = await apply(client, [one, edit("rounds", ids["rounds"][5], episode_end_round_id=ids["rounds"][3])])
        assert result.status_code == 200, result.text
        assert (await client.get(f"/api/chats/{ids['chat_id']}/memory")).status_code == 200
    run_api(database, scenario)


def test_delete_history_requires_related_repairs_and_renumbering(database, managed_history):
    ids = managed_history
    before = database_contents(database)
    async def scenario(client):
        assert (await apply(client, [remove("rounds", ids["rounds"][0])])).status_code == 409
        assert database_contents(database) == before
        ops = [remove("episodes", ids["episode"]),
               edit("rounds", ids["rounds"][5], episode_required=False, episode_start_round_id=None, episode_end_round_id=None),
               remove("rounds", ids["rounds"][0])]
        ops.extend(edit("rounds", rid, round_no=number) for number, rid in enumerate(ids["rounds"][1:], 1))
        result = await apply(client, ops)
        assert result.status_code == 200, result.text
        records = (await client.get(f"/api/chats/{ids['chat_id']}/rounds")).json()
        assert [record["round_no"] for record in records] == list(range(1, 7))
        assert records[0]["id"] == ids["rounds"][1]
    run_api(database, scenario)
    after = database_contents(database)
    assert len(after["state_snapshots"]) == len(before["state_snapshots"]) - 1
    assert not after["episodes"]


def test_delete_chat_cascades_but_preserves_library(database, managed_history):
    ids = managed_history
    async def scenario(client):
        result = await apply(client, [remove("chats", ids["chat_id"])])
        assert result.status_code == 200, result.text
        snapshot = (await client.get("/api/admin/data")).json()["tables"]
        assert [row["id"] for row in snapshot["characters"]] == [ids["source"]]
        assert [row["character_id"] for row in snapshot["character_scenes"]] == [ids["source"]]
        assert not any(snapshot[name] for name in TABLES if name not in ("characters", "character_scenes"))
    run_api(database, scenario)


def test_edit_primary_key_and_scope_rebuilds_all_references_atomically(database, managed_history):
    ids = managed_history
    before = database_contents(database)
    ops = [edit("chats", ids["chat_id"], id="renamed-chat")]
    for name, rows in before.items():
        for row in rows:
            if name != "chats" and row.get("chat_id") == ids["chat_id"]:
                key = {column.name: row[column.name] for column in TABLES[name].primary_key.columns}
                ops.append({"action": "update", "table": name, "key": key, "values": {"chat_id": "renamed-chat"}})
    async def scenario(client):
        result = await apply(client, ops)
        assert result.status_code == 200, result.text
        assert (await client.get("/api/chats/renamed-chat/archive")).status_code == 200
        assert (await client.get(f"/api/chats/{ids['chat_id']}/archive")).status_code == 404
        assert (await client.get("/api/admin/data?include_secrets=true")).json()["tables"]["model_configs"][0]["api_key"] == "admin-private-key"
    run_api(database, scenario)


@pytest.mark.parametrize("case", ["missing_state", "missing_initial", "missing_character", "missing_identity",
    "gap", "pending_old", "missing_episode", "future_episode", "skip_history", "premature_state"])
def test_inconsistent_graph_is_rejected_and_entire_batch_rolled_back(database, managed_history, case):
    ids = managed_history
    before = database_contents(database)
    initial = next(row["id"] for row in before["state_snapshots"] if row["round_id"] is None)
    identity = before["user_identities"][0]["id"]
    operations = {
        "missing_state": [remove("state_snapshots", ids["states"][0])],
        "missing_initial": [remove("state_snapshots", initial)],
        "missing_character": [remove("characters", ids["character_id"])],
        "missing_identity": [remove("user_identities", identity)],
        "gap": [edit("rounds", ids["rounds"][-1], round_no=20)],
        "pending_old": [edit("rounds", ids["rounds"][0], archive_step="episode_decision", episode_required=None)],
        "missing_episode": [remove("episodes", ids["episode"])],
        "future_episode": [edit("episodes", ids["episode"], end_round_id=ids["rounds"][5]),
                           edit("rounds", ids["rounds"][5], episode_end_round_id=ids["rounds"][5])],
        "skip_history": [edit("episodes", ids["episode"], start_round_id=ids["rounds"][1]),
                         edit("rounds", ids["rounds"][5], episode_start_round_id=ids["rounds"][1])],
        "premature_state": [edit("rounds", ids["rounds"][-1], archive_step="state_update", summary=None, episode_required=None)],
    }[case]
    async def scenario(client):
        result = await apply(client, [edit("chats", ids["chat_id"], title="不应部分保存")] + operations)
        assert result.status_code == 409, result.text
    run_api(database, scenario)
    assert database_contents(database) == before


@pytest.mark.parametrize("values", [
    {"round_no": "3"}, {"round_no": True}, {"round_no": 0}, {"archive_step": "invalid"},
    {"summary": " \t\n"}, {"user_input": None}, {"created_at": "2026-10-19T00:00:00"},
    {"created_at": 123}, {"unknown": "admin-private-key"}, {"id": "x" * 37},
])
def test_invalid_fields_never_expose_submitted_values(database, managed_history, values):
    ids, before = managed_history, database_contents(database)
    async def scenario(client):
        result = await apply(client, [edit("rounds", ids["rounds"][0], **values)])
        assert result.status_code == 422 and "admin-private-key" not in result.text
    run_api(database, scenario)
    assert database_contents(database) == before


def test_binding_composite_key_and_model_key_updates(database, managed_history):
    ids = managed_history
    async def scenario(client):
        key = {"chat_id": ids["chat_id"], "purpose": "writing"}
        for invalid in ({"chat_id": ids["chat_id"]}, {"chat_id": ids["chat_id"], "purpose": "writing", "extra": "x"}):
            result = await apply(client, [{"action": "delete", "table": "chat_model_bindings", "key": invalid}])
            assert result.status_code == 422
        result = await apply(client, [
            {"action": "update", "table": "chat_model_bindings", "key": key, "values": {"purpose": "state_update"}},
            edit("model_configs", ids["model"], api_key="new-private-key"),
        ])
        assert result.status_code == 200 and "new-private-key" not in result.text
        result = await apply(client, [edit("model_configs", ids["model"], name="只改名称")])
        assert result.status_code == 200
        full = (await client.get("/api/admin/data?include_secrets=true")).json()["tables"]
        assert full["model_configs"][0]["api_key"] == "new-private-key"
        assert full["chat_model_bindings"][0]["purpose"] == "state_update"
        assert (await apply(client, [edit("model_configs", ids["model"], api_key="")])).status_code == 200
        masked = (await client.get("/api/admin/data")).json()["tables"]
        assert masked["model_configs"][0]["has_api_key"] is False
        assert (await apply(client, [remove("model_configs", ids["model"])])).status_code == 200
        assert not (await client.get("/api/admin/data")).json()["tables"]["chat_model_bindings"]
    run_api(database, scenario)


def test_stale_revision_rejects_even_unrelated_or_secret_changes(database, managed_history):
    ids = managed_history
    async def scenario(client):
        old = (await client.get("/api/admin/data")).json()["revision"]
        with database.transaction() as session:
            Repository(session).get(ModelConfig, ids["model"]).api_key = "changed-elsewhere"
        before = database_contents(database)
        result = await apply(client, [edit("chats", ids["chat_id"], title="旧页面提交")], old)
        assert result.status_code == 409
        assert database_contents(database) == before
        assert (await client.get("/api/admin/data")).json()["revision"] != old
    run_api(database, scenario)


def test_concurrent_batches_with_same_revision_only_one_succeeds(database, managed_history):
    ids, barrier = managed_history, Barrier(2)
    with database.read() as session:
        revision = AdminService(AdminRepository(session)).snapshot().revision
    def change(title):
        barrier.wait(timeout=5)
        try:
            with database.transaction() as session:
                AdminService(AdminRepository(session)).apply(AdminBatch.model_validate({
                    "expected_revision": revision, "operations": [edit("chats", ids["chat_id"], title=title)],
                }))
            return "saved"
        except ConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, ["修改甲", "修改乙"])) == ["conflict", "saved"]


def test_missing_record_and_sql_constraint_failure_roll_back_prior_operations(database, managed_history):
    ids, before = managed_history, database_contents(database)
    async def scenario(client):
        for invalid, status in [(remove("rounds", "missing"), 404),
                                (create("characters", chat_id=ids["chat_id"], name="重复副本"), 409)]:
            result = await apply(client, [edit("chats", ids["chat_id"], title="不应保存"), invalid])
            assert result.status_code == status, result.text
            assert "admin-private-key" not in result.text
            assert database_contents(database) == before
    run_api(database, scenario)


def test_unknown_tables_and_raw_sql_are_not_accepted(database, managed_history):
    before = database_contents(database)
    async def scenario(client):
        for operation in (create("alembic_version", version_num="bad"), create("sqlite_master", sql="DROP TABLE chats"),
                          {"action": "sql", "table": "chats", "sql": "DELETE FROM chats"}):
            assert (await apply(client, [operation])).status_code == 422
        revision = (await client.get("/api/admin/data")).json()["revision"]
        assert (await client.post("/api/admin/data", json={"expected_revision": revision, "operations": []})).status_code == 422
    run_api(database, scenario)
    assert database_contents(database) == before


def test_generated_identifiers_defaults_and_noop_update(database, managed_history):
    ids = managed_history
    async def scenario(client):
        revision = (await client.get("/api/admin/data")).json()["revision"]
        noop = await apply(client, [edit("chats", ids["chat_id"])])
        assert noop.status_code == 200 and noop.json()["revision"] == revision
        result = await apply(client, [create("user_identities", name="新来源身份")])
        assert result.status_code == 200, result.text
        rid = result.json()["changes"][0]["key"]["id"]
        assert len(rid) == 36
        row = next(row for row in (await client.get("/api/admin/data")).json()["tables"]["user_identities"] if row["id"] == rid)
        assert row["chat_id"] is None and row["description"] == "" and row["avatar"] is None
        assert row["created_at"].endswith("+00:00")
    run_api(database, scenario)


@pytest.mark.parametrize("case", ["model_scope", "preset_scope", "state_scope", "definition_owners", "missing_parent"])
def test_storage_references_and_definition_owners_remain_enforced(database, managed_history, case):
    ids = managed_history
    before = database_contents(database)
    operations = {
        "model_scope": [edit("model_configs", ids["model"], chat_id=None)],
        "preset_scope": [create("writing_presets", id="library-preset", name="来源预设", source=""),
                         edit("chats", ids["chat_id"], writing_preset_id="library-preset")],
        "state_scope": [edit("state_snapshots", ids["states"][0], character_id=ids["source"])],
        "definition_owners": [create("definitions", character_id=ids["character_id"],
                                     user_identity_id=before["user_identities"][0]["id"], content="双重归属")],
        "missing_parent": [create("definitions", character_id="absent", content="缺失归属")],
    }[case]
    async def scenario(client):
        result = await apply(client, operations)
        assert result.status_code == 409, result.text
    run_api(database, scenario)
    assert database_contents(database) == before


@pytest.mark.parametrize("start_index,end_index,status", [(5, 6, 200), (4, 6, 409), (6, 6, 409), (5, 7, 409)])
def test_pending_episode_range_starts_at_coverage_boundary(database, managed_history, start_index, end_index, status):
    ids = managed_history
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        record = repo.create_round(ids["chat_id"], "第八回合", "原文")
        rid = record.id
        repo.save_state(rid, {})
        repo.save_summary(rid, "摘要")
    all_rounds = ids["rounds"] + [rid]
    async def scenario(client):
        before = (await client.get("/api/admin/data")).json()
        result = await apply(client, [edit("rounds", rid, archive_step="episode_summary", episode_required=True,
                                          episode_start_round_id=all_rounds[start_index], episode_end_round_id=all_rounds[end_index])])
        assert result.status_code == status, result.text
        if status != 200:
            assert (await client.get("/api/admin/data")).json() == before
    run_api(database, scenario)


@pytest.mark.parametrize("start_index", [4, 5, 6])
def test_multiple_episode_ranges_cannot_overlap_or_skip_unrepresented_history(database, managed_history, start_index):
    ids = managed_history
    with database.transaction() as session:
        repo = ArchiveRepository(session)
        rid = repo.create_round(ids["chat_id"], "第八回合", "原文").id
        repo.save_state(rid, {})
        repo.save_summary(rid, "摘要")
        repo.save_decision(rid, start_round_id=ids["rounds"][5], end_round_id=ids["rounds"][6])
        episode_id = repo.save_episode(rid, "第二个情节").id
    async def scenario(client):
        before = (await client.get("/api/admin/data")).json()
        result = await apply(client, [edit("episodes", episode_id, start_round_id=ids["rounds"][start_index]),
                                     edit("rounds", rid, episode_start_round_id=ids["rounds"][start_index])])
        assert result.status_code == (200 if start_index == 5 else 409), result.text
        if start_index != 5:
            assert (await client.get("/api/admin/data")).json() == before
    run_api(database, scenario)


@pytest.mark.parametrize("content", [[], None, {"数字": float("nan")}, {"数字": float("inf")}])
def test_state_requires_finite_json_object(database, managed_history, content):
    import json
    ids, before = managed_history, database_contents(database)
    async def scenario(client):
        revision = (await client.get("/api/admin/data")).json()["revision"]
        body = {"expected_revision": revision, "operations": [edit("state_snapshots", ids["states"][0], content=content)]}
        result = await client.post("/api/admin/data", content=json.dumps(body), headers={"content-type": "application/json"})
        assert result.status_code == 422, result.text
    run_api(database, scenario)
    assert database_contents(database) == before


def test_failure_after_mutation_before_commit_rolls_back(database, managed_history, monkeypatch):
    ids, before = managed_history, database_contents(database)
    original = AdminRepository.update
    def interrupt(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("批量修改提交前中断")
    monkeypatch.setattr(AdminRepository, "update", interrupt)
    with database.read() as session:
        revision = AdminService(AdminRepository(session)).snapshot().revision
    with pytest.raises(RuntimeError):
        with database.transaction() as session:
            AdminService(AdminRepository(session)).apply(AdminBatch.model_validate({
                "expected_revision": revision, "operations": [edit("chats", ids["chat_id"], title="不保存")],
            }))
    assert database_contents(database) == before
