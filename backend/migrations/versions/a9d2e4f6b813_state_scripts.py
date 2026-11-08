"""Character state scripts."""

from alembic import op
import sqlalchemy as sa

revision = "a9d2e4f6b813"
down_revision = "b4e6d8f0a259"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("characters", sa.Column("state_script", sa.Text(), nullable=False, server_default=""))
    op.add_column("characters", sa.Column("state_script_history", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    # Plain DROP COLUMN: a batch rebuild of characters would cascade-delete its dependent rows.
    op.drop_column("characters", "state_script_history")
    op.drop_column("characters", "state_script")
