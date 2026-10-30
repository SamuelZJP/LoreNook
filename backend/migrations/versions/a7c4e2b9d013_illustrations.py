"""Add image workflows, per-chat illustration settings and generated illustrations.

Revision ID: a7c4e2b9d013
Revises: f1a2c3d4e5b6
"""

from alembic import op
import sqlalchemy as sa


revision = "a7c4e2b9d013"
down_revision = "f1a2c3d4e5b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_workflows",
        sa.Column("chat_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("workflow", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("instructions", sa.Text(), server_default="", nullable=False),
        sa.Column("width", sa.Integer(), server_default="1344", nullable=False),
        sa.Column("height", sa.Integer(), server_default="768", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("json_valid(workflow) AND json_type(workflow) = 'object'",
                           name=op.f("ck_image_workflows_workflow_object")),
        sa.CheckConstraint("width BETWEEN 64 AND 8192 AND height BETWEEN 64 AND 8192",
                           name=op.f("ck_image_workflows_image_size")),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], name=op.f("fk_image_workflows_chat_id_chats"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_workflows")),
        sa.UniqueConstraint("id", "chat_id", name=op.f("uq_image_workflows_id")),
    )
    with op.batch_alter_table("image_workflows") as batch:
        batch.create_index(batch.f("ix_image_workflows_chat_id"), ["chat_id"], unique=False)

    op.create_table(
        "chat_illustration_settings",
        sa.Column("chat_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=16), server_default="off", nullable=False),
        sa.Column("image_workflow_id", sa.String(length=36), nullable=True),
        sa.Column("model_config_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint("mode IN ('off', 'every_round', 'scene_change', 'manual')",
                           name=op.f("ck_chat_illustration_settings_valid_mode")),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], name=op.f("fk_chat_illustration_settings_chat_id_chats"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_workflow_id", "chat_id"], ["image_workflows.id", "image_workflows.chat_id"],
                                name=op.f("fk_chat_illustration_settings_image_workflow_id_image_workflows")),
        sa.ForeignKeyConstraint(["model_config_id", "chat_id"], ["model_configs.id", "model_configs.chat_id"],
                                name=op.f("fk_chat_illustration_settings_model_config_id_model_configs")),
        sa.PrimaryKeyConstraint("chat_id", name=op.f("pk_chat_illustration_settings")),
    )

    op.create_table(
        "illustrations",
        sa.Column("chat_id", sa.String(length=36), nullable=False),
        sa.Column("round_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("hidden", sa.Boolean(create_constraint=True, name="hidden_bool"), server_default="0", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'prompting', 'rendering', 'ready', 'failed')",
                           name=op.f("ck_illustrations_valid_status")),
        sa.CheckConstraint("status != 'ready' OR (file_name IS NOT NULL AND media_type IS NOT NULL)",
                           name=op.f("ck_illustrations_ready_file")),
        sa.CheckConstraint("status != 'failed' OR error IS NOT NULL", name=op.f("ck_illustrations_failed_error")),
        sa.CheckConstraint("prompt IS NULL OR (json_valid(prompt) AND json_type(prompt) = 'object')",
                           name=op.f("ck_illustrations_prompt_object")),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], name=op.f("fk_illustrations_chat_id_chats"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id", "chat_id"], ["rounds.id", "rounds.chat_id"],
                                name=op.f("fk_illustrations_round_id_rounds"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_illustrations")),
    )
    with op.batch_alter_table("illustrations") as batch:
        batch.create_index(batch.f("ix_illustrations_round_id"), ["round_id"], unique=False)
        batch.create_index("uq_illustrations_one_active", ["round_id"], unique=True,
                           sqlite_where=sa.text("status IN ('pending', 'prompting', 'rendering')"))


def downgrade():
    with op.batch_alter_table("illustrations") as batch:
        batch.drop_index("uq_illustrations_one_active",
                         sqlite_where=sa.text("status IN ('pending', 'prompting', 'rendering')"))
        batch.drop_index(batch.f("ix_illustrations_round_id"))
    op.drop_table("illustrations")
    op.drop_table("chat_illustration_settings")
    with op.batch_alter_table("image_workflows") as batch:
        batch.drop_index(batch.f("ix_image_workflows_chat_id"))
    op.drop_table("image_workflows")
