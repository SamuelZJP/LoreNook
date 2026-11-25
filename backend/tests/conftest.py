from backend.tests.state_fixtures import WORLD
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from backend.config import PROJECT_ROOT, Settings
from backend.modules.accounts.passwords import hash_password
from backend.repository.database import Database
from backend.repository.models import Character, CharacterScene, Chat, StateSnapshot, User, UserIdentity
from backend.repository.queries import Repository
from backend.shared.scope import scoped, user_scope

TEST_USERNAME, TEST_PASSWORD = "tester", "test-password"
_TEST_HASH = hash_password(TEST_PASSWORD)


def add_user(database: Database, username: str, role: str = "user", password_hash: str = _TEST_HASH) -> str:
    with database.transaction() as session:
        user = User(username=username, password_hash=password_hash, role=role)
        session.add(user)
        session.flush()
        return user.id


async def sign_in(client, username: str = TEST_USERNAME, password: str = TEST_PASSWORD):
    """Clients must use an https base URL: the session cookie is Secure."""
    response = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response


def migration_config(path: Path) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}".replace("%", "%%"))
    return config


@pytest.fixture(autouse=True)
def administrator_scope():
    """Code under test runs as an administrator unless a test sets another scope (model calls may reach test hosts)."""
    with scoped(user_scope("test-administrator", is_admin=True)):
        yield


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "test.db"
    command.upgrade(migration_config(path), "head")
    db = Database(Settings(database_url=f"sqlite:///{path.as_posix()}"))
    # Tests act as one administrator unless they set another scope.
    user_id = add_user(db, TEST_USERNAME, "admin")
    with scoped(user_scope(user_id, is_admin=True)):
        yield db
    db.dispose()


@pytest.fixture
def chat(database):
    with database.transaction() as session:
        repo = Repository(session)
        chat = repo.add(Chat(title="测试聊天"))
        character = repo.add(Character(chat_id=chat.id, name="角色"))
        repo.add(CharacterScene(character_id=character.id, name="默认"))
        repo.add(UserIdentity(chat_id=chat.id, name="身份"))
        repo.add(StateSnapshot(chat_id=chat.id, character_id=character.id,
                               content={"世界": dict(WORLD), "年龄": 16}))
        return chat.id, character.id
