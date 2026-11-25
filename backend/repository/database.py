"""SQLite connections and explicit, short units of work."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import Settings
from backend.repository import ownership


class Database:
    def __init__(self, settings: Settings):
        url = settings.resolved_database_url()
        path = make_url(url).database
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        options = {"poolclass": StaticPool} if path in (None, ":memory:", "") else {}
        self.engine = create_engine(
            url, connect_args={"check_same_thread": False}, **options
        )

        @event.listens_for(self.engine, "connect")
        def configure_connection(connection, _record):
            # SQLAlchemy controls BEGIN, including DDL and SAVEPOINT transactions.
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms:d}")
            cursor.close()

        @event.listens_for(self.engine, "begin")
        def begin(connection):
            mode = connection.get_execution_options().get("sqlite_begin_mode", "DEFERRED")
            connection.exec_driver_sql(f"BEGIN {mode}")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        ownership.install(self.sessions)

    @contextmanager
    def read(self) -> Iterator[Session]:
        """Close and roll back the read session on exit; never commit writes."""
        with self.sessions() as session:
            yield session

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Serialize local writers before reading; commit everything or nothing."""
        with self.sessions() as session:
            with session.begin():
                session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
                yield session

    def dispose(self) -> None:
        self.engine.dispose()
