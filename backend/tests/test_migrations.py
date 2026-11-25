import asyncio

import httpx
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from backend.config import Settings
from backend.main import create_app
from backend.repository.archive import ArchiveRepository
from backend.repository.models import Base, Character, Chat, WritingPreset
from backend.repository.queries import Repository
from backend.tests.conftest import migration_config


def test_migration_matches_models_and_downgrade_with_data(database, tmp_path):
    with database.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with database.transaction() as session:
        repo = Repository(session)
        chat = repo.add(Chat(title="有数据的数据库"))
        repo.add(Character(chat_id=chat.id, name="角色"))
        preset = repo.add(WritingPreset(chat_id=chat.id, name="预设", source="源码"))
        chat.writing_preset_id = preset.id
        archive = ArchiveRepository(session)
        first = archive.create_round(chat.id, "输入一", "输出一")
        archive.save_state(first.id, {})
        archive.save_summary(first.id, "摘要一")
        archive.save_decision(first.id)
        second = archive.create_round(chat.id, "输入二", "输出二")
        archive.save_state(second.id, {})
        archive.save_summary(second.id, "摘要二")
        archive.save_decision(second.id, start_round_id=first.id, end_round_id=first.id)
        archive.save_episode(second.id, "情节摘要")
    database.dispose()
    config = migration_config(tmp_path / "test.db")
    command.downgrade(config, "base")
    assert inspect(database.engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert set(inspect(database.engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}


def test_health_and_application_lifecycle(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{(tmp_path / 'app.db').as_posix()}"))

    async def check():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get("/health")).json() == {"status": "ok"}
                assert app.state.database is not None

    asyncio.run(check())


def test_accounts_migration_gives_existing_data_to_the_administrator(tmp_path, monkeypatch):
    import pytest
    from sqlalchemy import create_engine, text

    from backend.modules.accounts.passwords import verify_password

    path = tmp_path / "legacy.db"
    config = migration_config(path)
    command.upgrade(config, "d4b7e2a9c615")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO chats (id, title) VALUES ('c1', '旧聊天')"))
        connection.execute(text("INSERT INTO user_identities (id, name) VALUES ('i1', '旧身份')"))
        connection.execute(text("INSERT INTO chat_templates (id, name, is_default) VALUES ('t1', '旧模板', 1)"))
    media = tmp_path / "media"
    media.mkdir()
    (media / ("a" * 64 + ".png")).write_bytes(b"png")
    (media / "notes.txt").write_text("not an upload")
    monkeypatch.setenv("LORENOOK_MEDIA_DIRECTORY", str(media))
    monkeypatch.delenv("LORENOOK_ADMIN_USERNAME", raising=False)
    with pytest.raises(RuntimeError, match="LORENOOK_ADMIN_USERNAME"):
        command.upgrade(config, "head")
    monkeypatch.setenv("LORENOOK_ADMIN_USERNAME", "keeper")
    monkeypatch.setenv("LORENOOK_ADMIN_PASSWORD", "keeper-password")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        admin_id, role, password_hash = connection.execute(
            text("SELECT id, role, password_hash FROM users WHERE username = 'keeper'")).one()
        assert role == "admin" and verify_password("keeper-password", password_hash)
        for table in ("chats", "user_identities", "chat_templates"):
            assert connection.execute(text(f"SELECT DISTINCT owner_id FROM {table}")).scalars().all() == [admin_id]
        assert connection.execute(text("SELECT name, owner_id FROM media_files")).all() == [("a" * 64 + ".png", admin_id)]
    engine.dispose()
    command.downgrade(config, "d4b7e2a9c615")


def test_accounts_migration_on_an_empty_database_needs_no_administrator(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    monkeypatch.delenv("LORENOOK_ADMIN_USERNAME", raising=False)
    path = tmp_path / "empty.db"
    command.upgrade(migration_config(path), "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
    engine.dispose()
