"""Move First Message into per-character opening scenes with initial-state overrides.

Revision ID: f1a2c3d4e5b6
Revises: e36b9c7210af
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "f1a2c3d4e5b6"
down_revision = "e36b9c7210af"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_scenes",
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("first_message", sa.Text(), server_default="", nullable=False),
        sa.Column("initial_state", sa.JSON(none_as_null=True), server_default="{}", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint('"order" >= 0', name=op.f("ck_character_scenes_nonnegative_order")),
        sa.CheckConstraint("json_valid(initial_state) AND json_type(initial_state) = 'object'",
                           name=op.f("ck_character_scenes_initial_state_object")),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"],
                                name=op.f("fk_character_scenes_character_id_characters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_character_scenes")),
    )
    with op.batch_alter_table("character_scenes") as batch:
        batch.create_index(batch.f("ix_character_scenes_character_id"), ["character_id"], unique=False)
    connection = op.get_bind()
    scenes = sa.table("character_scenes", sa.column("id"), sa.column("character_id"), sa.column("order"),
                      sa.column("name"), sa.column("description"), sa.column("first_message"),
                      sa.column("initial_state"))
    rows = connection.execute(sa.text("SELECT id, first_message FROM characters")).all()
    if rows:
        connection.execute(scenes.insert(), [
            {"id": str(uuid4()), "character_id": row.id, "order": 0, "name": "默认", "description": "",
             "first_message": row.first_message, "initial_state": "{}"} for row in rows
        ])
    # Native DROP COLUMN: a batch table rebuild would cascade-delete the scenes just inserted.
    op.execute("ALTER TABLE characters DROP COLUMN first_message")


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text(
        "SELECT 1 FROM character_scenes GROUP BY character_id HAVING count(*) > 1 "
        "UNION ALL SELECT 1 FROM character_scenes WHERE initial_state != '{}' LIMIT 1"
    )).first() is not None:
        raise ValueError("Cannot downgrade while characters have multiple scenes or initial-state overrides")
    op.execute("ALTER TABLE characters ADD COLUMN first_message TEXT DEFAULT '' NOT NULL")
    connection.execute(sa.text(
        "UPDATE characters SET first_message = coalesce((SELECT first_message FROM character_scenes "
        "WHERE character_scenes.character_id = characters.id), '')"
    ))
    with op.batch_alter_table("character_scenes") as batch:
        batch.drop_index(batch.f("ix_character_scenes_character_id"))
    op.drop_table("character_scenes")
