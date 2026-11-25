"""Demo links: the `demo` role and the table of links."""

from alembic import op
import sqlalchemy as sa

revision = "b7d3f9a1c264"
down_revision = "e8a1c4f7b302"
branch_labels = None
depends_on = None


def _roles(roles: str) -> None:
    # Rebuilding `users` drops it, which cascades to login_sessions; keep them so nobody is signed out.
    connection = op.get_bind()
    sessions = [dict(row) for row in connection.execute(sa.text("SELECT * FROM login_sessions")).mappings()]
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(batch.f("ck_users_valid_role"), type_="check")
        batch.create_check_constraint(batch.f("ck_users_valid_role"), f"role IN ({roles})")
    connection.execute(sa.text("DELETE FROM login_sessions"))
    if sessions:
        table = sa.table("login_sessions", *(sa.column(name) for name in sessions[0]))
        connection.execute(sa.insert(table), sessions)


def upgrade():
    _roles("'admin', 'user', 'demo'")
    op.create_table(
        "demo_passes",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("open_before", sa.DateTime(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("rounds_limit", sa.Integer(), nullable=False),
        sa.Column("images_limit", sa.Integer(), nullable=False),
        sa.Column("rounds_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("images_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("purged_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("minutes > 0 AND rounds_limit >= 0 AND images_limit >= 0",
                           name=op.f("ck_demo_passes_positive_limits")),
        sa.CheckConstraint("(redeemed_at IS NULL) = (expires_at IS NULL) AND (redeemed_at IS NULL) = (user_id IS NULL)",
                           name=op.f("ck_demo_passes_redeemed_together")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_demo_passes_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_passes")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_demo_passes_token_hash")),
        sa.UniqueConstraint("user_id", name=op.f("uq_demo_passes_user_id")),
    )


def downgrade():
    op.drop_table("demo_passes")
    op.execute("UPDATE users SET disabled = 1 WHERE role = 'demo'")
    op.execute("DELETE FROM login_sessions WHERE user_id IN (SELECT id FROM users WHERE role = 'demo')")
    op.execute("UPDATE users SET role = 'user' WHERE role = 'demo'")
    _roles("'admin', 'user'")
