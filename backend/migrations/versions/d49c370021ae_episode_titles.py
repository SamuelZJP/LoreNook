"""Add titles to episode summaries while retaining legacy text unchanged."""

from alembic import op
import sqlalchemy as sa

revision = "d49c370021ae"
down_revision = "bc8b253579a2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("episodes", sa.Column("title", sa.Text(), nullable=False, server_default=""))


def downgrade():
    op.drop_column("episodes", "title")
