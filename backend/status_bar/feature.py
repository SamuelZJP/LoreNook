"""The feature's single connection to the application: routes, tables and the chat-created hook."""

from fastapi import FastAPI

from backend.repository.queries import Repository
from backend.status_bar.admin_tables import register_admin_tables
from backend.status_bar.api import router
from backend.status_bar.service import StatusBarService

register_admin_tables()


def install(app: FastAPI) -> None:
    app.include_router(router)


def start(app: FastAPI, configuration, database, client, **_):
    """No background services; only copies the card's status bar into new chats."""
    app.state.hooks.chat_created.append(lambda session, chat_id, payload:
                                        StatusBarService(Repository(session)).copy_for_chat(session, chat_id, payload))
    return lambda: None
