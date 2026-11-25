"""Built-in users, login sessions, and an owner on every user's rows.

Existing rows and uploaded images go to the administrator named by LORENOOK_ADMIN_USERNAME and
LORENOOK_ADMIN_PASSWORD, which must be set when the database has data. On an empty database the
administrator is created only if both are set.
"""

import os
import uuid

from alembic import op
import sqlalchemy as sa

from backend.config import Settings
from backend.modules.accounts.passwords import hash_password
from backend.modules.accounts.service import validate_credentials
from backend.modules.media import MEDIA_NAME

revision = "e8a1c4f7b302"
down_revision = "d4b7e2a9c615"
branch_labels = None
depends_on = None

OWNED = ("chats", "characters", "user_identities", "writing_presets", "model_configs", "chat_templates",
         "image_workflows")


def upgrade():
    op.create_table(
        "users",
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
        sa.Column("disabled", sa.Boolean(create_constraint=True, name="disabled_bool"), server_default="0",
                  nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'user')", name=op.f("ck_users_valid_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "login_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_login_sessions_user_id_users"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_login_sessions_token_hash")),
    )
    op.create_index(op.f("ix_login_sessions_user_id"), "login_sessions", ["user_id"], unique=False)
    op.create_table(
        "media_files",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("name", "owner_id", name=op.f("pk_media_files")),
    )

    # Plain ALTER TABLE: a batch rebuild would cascade-delete dependent rows.
    for table in OWNED:
        op.add_column(table, sa.Column("owner_id", sa.String(length=36), server_default="", nullable=False))
        op.create_index(op.f(f"ix_{table}_owner_id"), table, ["owner_id"], unique=False)
    op.drop_index("uq_chat_templates_one_default", table_name="chat_templates")
    op.create_index("uq_chat_templates_one_default", "chat_templates", ["owner_id", "is_default"], unique=True,
                    sqlite_where=sa.text("is_default = 1"))

    connection = op.get_bind()
    has_data = any(connection.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() for table in OWNED)
    username = os.getenv("LORENOOK_ADMIN_USERNAME", "").strip()
    password = os.getenv("LORENOOK_ADMIN_PASSWORD", "")
    if not (username and password):
        if has_data:
            raise RuntimeError("数据库已有数据：请设置 LORENOOK_ADMIN_USERNAME 和 LORENOOK_ADMIN_PASSWORD，"
                               "已有数据将归属这位管理员")
        return
    validate_credentials(username, password)
    admin_id = str(uuid.uuid4())
    connection.execute(sa.text("INSERT INTO users (id, username, password_hash, role) VALUES (:id, :name, :hash, 'admin')"),
                       {"id": admin_id, "name": username, "hash": hash_password(password)})
    for table in OWNED:
        connection.execute(sa.text(f"UPDATE {table} SET owner_id = :owner"), {"owner": admin_id})
    media = Settings().resolved_media_directory()
    names = sorted(path.name for path in media.iterdir() if MEDIA_NAME.fullmatch(path.name)) if media.is_dir() else []
    for name in names:
        connection.execute(sa.text("INSERT INTO media_files (name, owner_id) VALUES (:name, :owner)"),
                           {"name": name, "owner": admin_id})


def downgrade():
    connection = op.get_bind()
    # The single-default rule becomes global again: keep the oldest default.
    connection.execute(sa.text(
        "UPDATE chat_templates SET is_default = 0 WHERE is_default = 1 AND id NOT IN "
        "(SELECT id FROM chat_templates WHERE is_default = 1 ORDER BY created_at, id LIMIT 1)"))
    op.drop_index("uq_chat_templates_one_default", table_name="chat_templates")
    op.create_index("uq_chat_templates_one_default", "chat_templates", ["is_default"], unique=True,
                    sqlite_where=sa.text("is_default = 1"))
    for table in OWNED:
        op.drop_index(op.f(f"ix_{table}_owner_id"), table_name=table)
        op.drop_column(table, "owner_id")
    op.drop_table("media_files")
    op.drop_index(op.f("ix_login_sessions_user_id"), table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_table("users")
