"""Per model config request timeout."""

from alembic import op
import sqlalchemy as sa

revision = "b4e6d8f0a259"
down_revision = "c5e7a9d1f382"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("model_configs", sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"))


def downgrade():
    with op.batch_alter_table("model_configs") as batch:
        batch.drop_column("timeout_seconds")
