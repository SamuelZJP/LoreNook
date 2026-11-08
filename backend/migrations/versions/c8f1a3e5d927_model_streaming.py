"""Per model config streaming switch."""

from alembic import op
import sqlalchemy as sa

revision = "c8f1a3e5d927"
down_revision = "a9d2e4f6b813"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("model_configs") as batch:
        batch.add_column(sa.Column("streaming", sa.Boolean(create_constraint=True, name="streaming_bool"),
                                   server_default="0", nullable=False))


def downgrade():
    with op.batch_alter_table("model_configs") as batch:
        batch.drop_constraint(batch.f("ck_model_configs_streaming_bool"), type_="check")
        batch.drop_column("streaming")
