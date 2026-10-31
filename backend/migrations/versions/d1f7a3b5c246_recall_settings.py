"""Per-chat memory recall settings, owned by the recall feature."""

from alembic import op
import sqlalchemy as sa

revision = "d1f7a3b5c246"
down_revision = "b8d5f3c1e024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_recall_settings",
        sa.Column("chat_id", sa.String(length=36), nullable=False),
        sa.Column("model_config_id", sa.String(length=36), nullable=True),
        sa.Column("depth", sa.Integer(), server_default="3", nullable=False),
        sa.CheckConstraint("depth >= 0", name=op.f("ck_chat_recall_settings_depth_nonnegative")),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], name=op.f("fk_chat_recall_settings_chat_id_chats"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_config_id", "chat_id"], ["model_configs.id", "model_configs.chat_id"],
                                name=op.f("fk_chat_recall_settings_model_config_id_model_configs")),
        sa.PrimaryKeyConstraint("chat_id", name=op.f("pk_chat_recall_settings")),
    )


def downgrade():
    op.drop_table("chat_recall_settings")
