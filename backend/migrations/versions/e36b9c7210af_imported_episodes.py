"""Allow imported episodes without an archive creator.

Revision ID: e36b9c7210af
Revises: d49c370021ae
"""

from alembic import op
import sqlalchemy as sa


revision = "e36b9c7210af"
down_revision = "d49c370021ae"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("episodes") as batch:
        batch.alter_column("created_by_round_id", existing_type=sa.String(36), nullable=True)


def downgrade():
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM episodes WHERE created_by_round_id IS NULL LIMIT 1"
    )).first() is not None:
        raise ValueError("Cannot downgrade while imported episodes have no archive creator")
    with op.batch_alter_table("episodes") as batch:
        batch.alter_column("created_by_round_id", existing_type=sa.String(36), nullable=False)
