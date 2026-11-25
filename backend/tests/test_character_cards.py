import asyncio
import io
import json
import zipfile

import httpx
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.modules.character_cards.package import MAX_ENTRIES
from backend.tests.state_fixtures import STATE_SCHEMA, WORLD

PNG = b"\x89PNG\r\n\x1a\ncard-image"
WEBP = b"RIFF\x00\x00\x00\x00WEBPcard-image"
SCRIPT = "def process(state, previous, history):\n    return state\n"
STATUS_BAR = "<div>状态栏</div>"


def run(database, tmp_path, scenario):
    settings = Settings(database_url=database.engine.url.render_as_string(hide_password=False),
                        media_directory=str(tmp_path / "media"), image_directory=str(tmp_path / "images"))
    app = create_app(settings)

    async def main():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                await scenario(client)
    asyncio.run(main())


def zipped(card, media=None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("card.json", card if isinstance(card, (bytes, str)) else json.dumps(card, ensure_ascii=False))
        for path, data in (media or {}).items():
            archive.writestr(path, data)
    return buffer.getvalue()


def card(**character):
    return {"format": "lorenook.character", "version": 1,
            "character": {"name": "导入", "scenes": [{"name": "默认", "initial_state": {"世界": WORLD}}], **character}}


async def upload(client, data: bytes) -> str:
    return (await client.post("/api/media", content=data)).json()["url"]


async def full_character(client):
    avatar, portrait = await upload(client, PNG), await upload(client, WEBP)
    reference = (await client.post("/api/media", content=PNG)).json()["name"]
    character = (await client.post("/api/characters", json={
        "name": "江清月/测试", "avatar": avatar, "portrait": portrait, "description": "描述",
        "definitions": [{"order": 1, "content": "第二条", "enabled": False},
                        {"order": 0, "content": "{{ char }}", "has_template": True}],
        "scenes": [{"name": "教室", "first_message": "开场一", "initial_state": {"世界": {**WORLD, "地点": "教室"}}},
                   {"order": 1, "name": "校门", "description": "放学后", "first_message": "开场二"}],
        "state_schema": STATE_SCHEMA, "state_reference": "参考", "state_update_rules": "规则",
        "state_script": SCRIPT, "state_script_history": 3,
    })).json()
    await client.put(f"/api/characters/{character['id']}/cast", json={"members": [
        {"name": "江清月", "appearance": "黑发", "reference_image": reference}, {"name": "路人"}]})
    await client.put(f"/api/characters/{character['id']}/status-bar", json={"code": STATUS_BAR})
    return character


def comparable(character):
    return {key: value for key, value in character.items() if key not in {"id", "chat_id", "created_at"}} | {
        "definitions": [{k: v for k, v in d.items() if k not in {"id", "character_id"}} for d in character["definitions"]],
        "scenes": [{k: v for k, v in s.items() if k not in {"id", "character_id"}} for s in character["scenes"]],
    }


def test_export_then_import_keeps_the_whole_card(database, tmp_path):
    async def scenario(client):
        source = await full_character(client)
        response = await client.get(f"/api/characters/{source['id']}/card")
        assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
        assert "filename*=UTF-8''%E6%B1%9F%E6%B8%85%E6%9C%88%E6%B5%8B%E8%AF%95.lorenook" in response.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            written = json.loads(archive.read("card.json"))
            assert sorted(archive.namelist()) == ["card.json", *sorted(
                f"media/{name}" for name in {source["avatar"].rsplit("/", 1)[1], source["portrait"].rsplit("/", 1)[1]})]
        assert written["format"] == "lorenook.character" and written["version"] == 1
        assert written["character"]["avatar"].startswith("media/")
        assert [d["content"] for d in written["character"]["definitions"]] == ["{{ char }}", "第二条"]
        assert written["features"]["illustrations"]["cast"][0]["reference_image"] == written["character"]["avatar"]
        assert written["features"]["illustrations"]["cast"][1] == {"name": "路人", "appearance": "", "reference_image": None}
        assert written["features"]["status_bar"] == {"code": STATUS_BAR}

        summary = (await client.post("/api/character-cards/inspect", content=response.content)).json()
        assert summary == {"name": "江清月/测试", "scenes": 2, "has_state_schema": True, "has_state_script": True,
                           "features": ["illustrations", "status_bar"], "unknown_features": []}

        imported = await client.post("/api/character-cards/import?keep_code=true", content=response.content)
        assert imported.status_code == 201
        copy = imported.json()
        assert copy["id"] != source["id"] and copy["chat_id"] is None
        assert comparable(copy) == comparable((await client.get(f"/api/characters/{source['id']}")).json())
        cast = (await client.get(f"/api/characters/{copy['id']}/cast")).json()
        assert [(m["name"], m["appearance"]) for m in cast] == [("江清月", "黑发"), ("路人", "")]
        assert cast[0]["reference_image"] == source["avatar"].rsplit("/", 1)[1]
        assert (await client.get(f"/api/characters/{copy['id']}/status-bar")).json() == {"code": STATUS_BAR}
    run(database, tmp_path, scenario)


def test_import_without_code_drops_the_schema_and_script(database, tmp_path):
    async def scenario(client):
        # The scene relies on the Schema's defaults, so it would not pass on its own.
        data = zipped(card(state_schema=STATE_SCHEMA, state_script=SCRIPT,
                           scenes=[{"name": "默认", "initial_state": {"世界": {"地点": "教室"}}}]))
        imported = (await client.post("/api/character-cards/import", content=data)).json()
        assert imported["state_schema"] == "" and imported["state_script"] == ""
        assert imported["scenes"][0]["initial_state"] == {"世界": {"地点": "教室"}}

        # Without a Schema to drop, scenes are still checked.
        bad = zipped(card(scenes=[{"name": "默认", "initial_state": {"世界": {"地点": "教室"}}}]))
        assert (await client.post("/api/character-cards/import", content=bad)).status_code == 422
    run(database, tmp_path, scenario)


def test_chat_copy_exports_its_single_scene(database, tmp_path):
    async def scenario(client):
        source = await full_character(client)
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        chat = (await client.post("/api/chats", json={"title": "聊天", "character_id": source["id"],
                                                       "user_identity_id": identity["id"],
                                                       "scene_id": source["scenes"][1]["id"]})).json()
        response = await client.get(f"/api/chats/{chat['id']}/character/card")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            written = json.loads(archive.read("card.json"))
        assert [s["name"] for s in written["character"]["scenes"]] == ["校门"]
        assert written["features"]["status_bar"] == {"code": STATUS_BAR}
        # A chat's own character is not a library card.
        chat_character = (await client.get(f"/api/chats/{chat['id']}")).json()["character"]["id"]
        assert (await client.get(f"/api/characters/{chat_character}/card")).status_code == 404
    run(database, tmp_path, scenario)


def test_outside_avatar_urls_and_unknown_features(database, tmp_path):
    async def scenario(client):
        data = zipped(card(avatar="https://example.com/a.png") | {"features": {"someday": {"x": 1}}})
        summary = (await client.post("/api/character-cards/inspect", content=data)).json()
        assert summary["unknown_features"] == ["someday"] and summary["features"] == []
        imported = (await client.post("/api/character-cards/import", content=data)).json()
        assert imported["avatar"] == "https://example.com/a.png"
        assert (await client.get(f"/api/characters/{imported['id']}/cast")).json() == []
    run(database, tmp_path, scenario)


@pytest.mark.parametrize(("data", "message"), [
    (b"not a zip", "不是有效的角色卡文件"),
    (zipped({"format": "other"}), "不是 LoreNook 角色卡"),
    (zipped(card() | {"version": 2}), "角色卡版本 2 高于"),
    (zipped(b"{"), "不是有效的 JSON"),
    (zipped(card(name="")), "character.name"),
    (zipped(card(scenes=[])), "character.scenes"),
    (zipped(card(avatar="media/missing.png")), "缺少图片 media/missing.png"),
    (zipped(card(avatar="media/a.png"), {"media/a.png": b"not an image"}), "不是 PNG"),
    (zipped(card(), {"media/../x.png": PNG}), "路径无效"),
    (zipped(card() | {"features": {"illustrations": {"cast": [{"name": ""}]}}}), "功能数据 illustrations"),
    (zipped(card() | {"features": {"status_bar": []}}), "features.status_bar"),
])
def test_invalid_cards_are_refused(database, tmp_path, data, message):
    async def scenario(client):
        response = await client.post("/api/character-cards/import", content=data)
        assert response.status_code == 422 and message in response.json()["detail"]
        assert (await client.get("/api/characters")).json() == []
    run(database, tmp_path, scenario)


def test_missing_card_and_too_many_entries(database, tmp_path):
    async def scenario(client):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "x")
        assert "缺少 card.json" in (await client.post("/api/character-cards/inspect", content=buffer.getvalue())).json()["detail"]
        many = zipped(card(), {f"media/{n}.png": PNG for n in range(MAX_ENTRIES)})
        assert "文件过多" in (await client.post("/api/character-cards/inspect", content=many)).json()["detail"]
    run(database, tmp_path, scenario)


def test_a_failing_section_rolls_back_the_import(database, tmp_path):
    async def scenario(client):
        # Cast reference images must be package images, not outside URLs.
        data = zipped(card() | {"features": {"status_bar": {"code": STATUS_BAR},
                                             "illustrations": {"cast": [{"name": "甲", "reference_image": "https://x/y.png"}]}}})
        response = await client.post("/api/character-cards/import", content=data)
        assert response.status_code == 422
        assert (await client.get("/api/characters")).json() == []
    run(database, tmp_path, scenario)
