"""Status bar tables, owned by the status bar feature."""

from alembic import op
import sqlalchemy as sa

revision = "c5e7a9d1f382"
down_revision = "a3c6e8f0b157"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_status_bars",
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], name=op.f("fk_character_status_bars_character_id_characters"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("character_id", name=op.f("pk_character_status_bars")),
    )
    op.create_table(
        "chat_status_bar_settings",
        sa.Column("chat_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(create_constraint=True, name="enabled_bool"), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], name=op.f("fk_chat_status_bar_settings_chat_id_chats"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_id", name=op.f("pk_chat_status_bar_settings")),
    )


def downgrade():
    op.drop_table("chat_status_bar_settings")
    op.drop_table("character_status_bars")
