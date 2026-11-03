from backend.tests.state_fixtures import STATE_SCHEMA
from backend.tests.test_catalog_api import run_api

CODE = "<div id='bar'></div><script>lorenook.onData(d => bar.textContent = d.state.世界.地点)</script>"


def test_card_status_bar_is_copied_into_chats_and_edited_there(database):
    async def scenario(client):
        character = (await client.post("/api/characters", json={"name": "角色", "state_schema": STATE_SCHEMA})).json()
        identity = (await client.post("/api/user-identities", json={"name": "身份"})).json()
        card = f"/api/characters/{character['id']}/status-bar"
        assert (await client.get(card)).json() == {"code": ""}
        assert (await client.put(card, json={"code": CODE})).json() == {"code": CODE}

        created = (await client.post("/api/chats", json={
            "title": "聊天", "character_id": character["id"], "user_identity_id": identity["id"]})).json()
        chat = f"/api/chats/{created['id']}/status-bar"
        assert (await client.get(chat)).json() == {"code": CODE, "enabled": True}
        assert (await client.patch(chat, json={"enabled": False})).json() == {"code": CODE, "enabled": False}
        assert (await client.patch(chat, json={"code": "<p>改</p>"})).json() == {"code": "<p>改</p>", "enabled": False}
        # The library card is untouched, and blank code removes the chat's status bar.
        assert (await client.get(card)).json() == {"code": CODE}
        assert (await client.patch(chat, json={"code": "  "})).json() == {"code": "", "enabled": False}
        # A chat's own character is not a library card.
        chat_character = (await client.get(f"/api/chats/{created['id']}")).json()["character"]["id"]
        assert (await client.get(f"/api/characters/{chat_character}/status-bar")).status_code == 404
    run_api(database, scenario)
