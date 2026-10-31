"""Add a recall switch and per-pass limits. Chats that already chose a model keep recall on."""

from alembic import op
import sqlalchemy as sa

revision = "e2a8b4c6d357"
down_revision = "d1f7a3b5c246"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("chat_recall_settings") as batch:
        batch.add_column(sa.Column("enabled", sa.Boolean(create_constraint=True, name="enabled_bool"),
                                   server_default="0", nullable=False))
        batch.add_column(sa.Column("episode_limit", sa.Integer(), server_default="2", nullable=False))
        batch.add_column(sa.Column("summary_limit", sa.Integer(), server_default="5", nullable=False))
        batch.create_check_constraint(batch.f("ck_chat_recall_settings_limits_nonnegative"),
                                      "episode_limit >= 0 AND summary_limit >= 0")
    op.execute("UPDATE chat_recall_settings SET enabled = 1 WHERE model_config_id IS NOT NULL")


def downgrade():
    with op.batch_alter_table("chat_recall_settings") as batch:
        batch.drop_constraint(batch.f("ck_chat_recall_settings_limits_nonnegative"), type_="check")
        batch.drop_constraint(batch.f("ck_chat_recall_settings_enabled_bool"), type_="check")
        batch.drop_column("summary_limit")
        batch.drop_column("episode_limit")
        batch.drop_column("enabled")
