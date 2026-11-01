"""LoreNook no longer writes image prompts with a model: the workflow does that itself."""

from alembic import op
import sqlalchemy as sa

revision = "f3b9c5d7e468"
down_revision = "e2a8b4c6d357"
branch_labels = None
depends_on = None


def _status_rules(batch, statuses: str, active: str) -> None:
    batch.drop_index("uq_illustrations_one_active")
    batch.drop_constraint(batch.f("ck_illustrations_valid_status"), type_="check")
    batch.create_check_constraint(batch.f("ck_illustrations_valid_status"), f"status IN ({statuses})")
    batch.create_index("uq_illustrations_one_active", ["round_id"], unique=True, sqlite_where=sa.text(f"status IN ({active})"))


def upgrade():
    op.execute("UPDATE illustrations SET status = 'failed', error = '服务重启，任务已中断' WHERE status = 'prompting'")
    with op.batch_alter_table("illustrations") as batch:
        _status_rules(batch, "'pending', 'rendering', 'ready', 'failed'", "'pending', 'rendering'")
    with op.batch_alter_table("chat_illustration_settings") as batch:
        batch.drop_constraint(batch.f("fk_chat_illustration_settings_model_config_id_model_configs"), type_="foreignkey")
        batch.drop_column("model_config_id")
    # Native statement: this table is referenced elsewhere, so it must not be rebuilt.
    op.execute("ALTER TABLE image_workflows DROP COLUMN prompt_template")


def downgrade():
    op.add_column("image_workflows", sa.Column("prompt_template", sa.Text(), server_default="", nullable=False))
    with op.batch_alter_table("chat_illustration_settings") as batch:
        batch.add_column(sa.Column("model_config_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(batch.f("fk_chat_illustration_settings_model_config_id_model_configs"), "model_configs",
                                 ["model_config_id", "chat_id"], ["id", "chat_id"])
    with op.batch_alter_table("illustrations") as batch:
        _status_rules(batch, "'pending', 'prompting', 'rendering', 'ready', 'failed'", "'pending', 'prompting', 'rendering'")
