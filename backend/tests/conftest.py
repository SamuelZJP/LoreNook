from backend.tests.state_fixtures import WORLD
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from backend.config import PROJECT_ROOT, Settings
from backend.repository.database import Database
from backend.repository.models import Character, Chat, StateSnapshot, UserIdentity
from backend.repository.queries import Repository


def migration_config(path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "test.db"
    command.upgrade(migration_config(path), "head")
    db = Database(Settings(database_url=f"sqlite:///{path.as_posix()}"))
    yield db
    db.dispose()


@pytest.fixture
def chat(database):
    with database.transaction() as session:
        repo = Repository(session)
        chat = repo.add(Chat(title="测试聊天"))
        character = repo.add(Character(chat_id=chat.id, name="角色"))
        repo.add(UserIdentity(chat_id=chat.id, name="身份"))
        repo.add(StateSnapshot(chat_id=chat.id, character_id=character.id,
                               content={"世界": dict(WORLD), "年龄": 16}))
        return chat.id, character.id
