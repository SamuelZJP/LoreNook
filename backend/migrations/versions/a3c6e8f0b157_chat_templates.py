"""Chat templates: named starting values for the new-chat form."""

from alembic import op
import sqlalchemy as sa

revision = "a3c6e8f0b157"
down_revision = "f3b9c5d7e468"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_templates",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(create_constraint=True, name="default_bool"), server_default="0", nullable=False),
        sa.Column("settings", sa.JSON(none_as_null=True), server_default="{}", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("json_valid(settings) AND json_type(settings) = 'object'",
                           name=op.f("ck_chat_templates_settings_object")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_templates")),
    )
    op.create_index("uq_chat_templates_one_default", "chat_templates", ["is_default"], unique=True,
                    sqlite_where=sa.text("is_default = 1"))


def downgrade():
    op.drop_index("uq_chat_templates_one_default", table_name="chat_templates")
    op.drop_table("chat_templates")
