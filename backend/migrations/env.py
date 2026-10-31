"""Alembic uses the same SQLite connection policy as the application."""

from alembic import context

from backend.config import Settings
from backend.repository.database import Database
from backend import features as _features  # noqa: F401  (registers their tables)
from backend.repository.models import Base, UTCDateTime


def render_item(kind, item, autogen_context):
    if kind == "type" and isinstance(item, UTCDateTime):
        return "sa.DateTime()"
    return False


def settings() -> Settings:
    # Programmatic migrations can supply a URL without changing process environment.
    url = context.config.get_main_option("sqlalchemy.url")
    return Settings(database_url=url) if url else Settings()


if context.is_offline_mode():
    context.configure(url=settings().resolved_database_url(), target_metadata=Base.metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    database = Database(settings())
    try:
        with database.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata,
                              render_as_batch=True, compare_type=True, render_item=render_item)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()
