from backend.tests.test_catalog_api import run_api

SETTINGS = {"writing_preset_id": "preset", "model_bindings": {"writing": "model"}, "recent_rounds": 3,
            "features": {"recall": {"enabled": True, "depth": 2}}}


def test_templates_crud_and_single_default(database):
    async def scenario(client):
        first = (await client.post("/api/chat-templates", json={"name": "日常", "is_default": True,
                                                                 "settings": SETTINGS})).json()
        assert first["is_default"] and first["settings"]["recent_rounds"] == 3
        assert first["settings"]["min_summaries"] == 6
        assert first["settings"]["features"] == {"recall": {"enabled": True, "depth": 2}}

        second = (await client.post("/api/chat-templates", json={"name": "长篇", "is_default": True})).json()
        listed = (await client.get("/api/chat-templates")).json()
        assert [(t["name"], t["is_default"]) for t in listed] == [("日常", False), ("长篇", True)]

        patched = await client.patch(f"/api/chat-templates/{first['id']}", json={"is_default": True, "name": "日常二"})
        assert patched.status_code == 200, patched.text
        listed = (await client.get("/api/chat-templates")).json()
        assert [(t["name"], t["is_default"]) for t in listed] == [("日常二", True), ("长篇", False)]

        settings = await client.patch(f"/api/chat-templates/{second['id']}", json={"settings": {"recent_rounds": 9}})
        assert settings.json()["settings"]["recent_rounds"] == 9 and settings.json()["settings"]["features"] == {}

        assert (await client.patch(f"/api/chat-templates/{second['id']}", json={"name": None})).status_code == 422
        assert (await client.post("/api/chat-templates", json={"name": "坏", "settings": {"unknown": 1}})).status_code == 422
        assert (await client.post("/api/chat-templates", json={
            "name": "坏", "settings": {"model_bindings": {"unknown": "model"}}})).status_code == 422

        assert (await client.delete(f"/api/chat-templates/{first['id']}")).status_code == 204
        assert [t["name"] for t in (await client.get("/api/chat-templates")).json()] == ["长篇"]
        assert (await client.delete(f"/api/chat-templates/{first['id']}")).status_code == 404

    run_api(database, scenario)
