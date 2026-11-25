from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, text

from backend.config import PROJECT_ROOT
from backend.tests.conftest import migration_config
from backend.tests.test_catalog_api import run_api

SCHEMA = (PROJECT_ROOT / "backend/modules/state/examples/basic.py").read_text(encoding="utf-8")
NIGHT = {"世界": {"时间": "21:30", "地点": "教室"}, "角色": {"好感度": 40}}


def test_scenes_validate_through_schema_and_select_initial_state(database):
    async def scenario(client):
        bad = await client.post("/api/characters", json={"name": "角色", "state_schema": SCHEMA, "scenes": [
            {"name": "坏开场", "initial_state": {"角色": {"好感度": "很多"}}}]})
        assert bad.status_code == 422 and "坏开场" in bad.json()["detail"]
        assert (await client.post("/api/characters", json={"name": "角色", "scenes": []})).status_code == 422

        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": SCHEMA, "scenes": [
            {"name": "早晨", "first_message": "早"},
            {"order": 1, "name": "夜晚", "description": "晚自习", "first_message": "晚", "initial_state": NIGHT},
        ]})).json()
        assert [scene["name"] for scene in character["scenes"]] == ["早晨", "夜晚"]
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()

        preview = await client.post("/api/characters/initial-state-preview",
                                    json={"state_schema": SCHEMA, "initial_state": NIGHT})
        assert preview.status_code == 200
        assert preview.json()["世界"] == {"日期": "2026-10-19", "星期": "星期一", "时间": "21:30", "地点": "教室"}
        assert preview.json()["角色"]["好感度"] == 40

        created = (await client.post("/api/chats", json={
            "title": "夜晚", "character_id": character["id"], "scene_id": character["scenes"][1]["id"],
            "user_identity_id": identity["id"]})).json()
        assert created["latest_state"]["content"] == preview.json()
        assert [scene["first_message"] for scene in created["character"]["scenes"]] == ["晚"]
        default = (await client.post("/api/chats", json={
            "title": "默认", "character_id": character["id"], "user_identity_id": identity["id"]})).json()
        assert default["character"]["scenes"][0]["name"] == "早晨"
        assert default["latest_state"]["content"]["世界"]["时间"] == "08:00"

        # A Schema edit must keep every scene valid, including ones not sent in the patch.
        breaking = SCHEMA.replace("class CharacterState(StateNode):", "class CharacterState(StateNode):\n    model_config = {'extra': 'forbid'}\n    新字段: int\n")
        response = await client.patch(f"/api/characters/{character['id']}", json={"state_schema": breaking})
        assert response.status_code == 422
        unchanged = (await client.get(f"/api/characters/{character['id']}")).json()
        assert unchanged["state_schema"] == SCHEMA and len(unchanged["scenes"]) == 2
    run_api(database, scenario)


def test_migration_moves_first_message_into_default_scene(tmp_path, monkeypatch):
    monkeypatch.setenv("LORENOOK_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LORENOOK_ADMIN_PASSWORD", "admin-password")
    path: Path = tmp_path / "legacy.db"
    config = migration_config(path)
    command.upgrade(config, "e36b9c7210af")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO characters (id, name, first_message) VALUES ('c1', '角色', '旧开场')"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT character_id, \"order\", name, first_message, initial_state FROM character_scenes")).all()
        assert [tuple(row) for row in rows] == [("c1", 0, "默认", "旧开场", "{}")]
    command.downgrade(config, "e36b9c7210af")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT first_message FROM characters")).scalar_one() == "旧开场"
    engine.dispose()
