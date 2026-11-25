"""Upright portrait for characters and user identities."""

from alembic import op
import sqlalchemy as sa

revision = "d4b7e2a9c615"
down_revision = "c8f1a3e5d927"
branch_labels = None
depends_on = None

TABLES = ("characters", "user_identities")


# Plain ALTER TABLE: a batch rebuild of characters would cascade-delete its scenes.
def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("portrait", sa.Text(), nullable=True))


def downgrade():
    for table in TABLES:
        op.drop_column(table, "portrait")
