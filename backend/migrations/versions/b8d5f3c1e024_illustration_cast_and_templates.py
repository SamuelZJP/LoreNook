"""Prompt templates per image workflow, cast members, identity appearance and main-character choice.

Revision ID: b8d5f3c1e024
Revises: a7c4e2b9d013
"""

from alembic import op
import sqlalchemy as sa


revision = "b8d5f3c1e024"
down_revision = "a7c4e2b9d013"
branch_labels = None
depends_on = None

# The default template as of this revision, with the old instructions kept as its requirements.
_TEMPLATE_HEAD = "## 提示词要求\n"
_TEMPLATE_TAIL = """

## 主要人物（画面以这些人为中心，人数越少效果越好）
{% for person in focus %}- {{ person.name }}：{{ person.appearance or '（没有外貌描述，依据设定）' }}
{% endfor %}
{% if others %}## 其他人物（除非本回合确实需要，否则不要入画）
{% for person in others %}- {{ person.name }}{% if person.appearance %}：{{ person.appearance }}{% endif %}
{% endfor %}
{% endif %}## 角色设定
{% for item in definitions.character %}{{ item }}

{% else %}（无）

{% endfor %}## 用户角色设定
{% for item in definitions.user %}{{ item }}

{% else %}（无）

{% endfor %}## 当前状态（本回合结束时，YAML）
{{ state_yaml }}
## 本回合摘要
{{ round.summary or '（无）' }}

## 本回合内容
用户输入：{{ round.user_input }}
AI正文：{{ round.content }}

## 任务
选取本回合最具代表性、最适合入画的一个瞬间，写出主要人物的外貌、衣着、姿态、表情，以及场景、时间、光线和氛围。外貌以上面的描述和设定为准，不确定的细节不要编造。"""


def upgrade():
    # Native statements: nothing here needs a table rebuild, and these tables are referenced elsewhere.
    op.add_column("image_workflows", sa.Column("prompt_template", sa.Text(), server_default="", nullable=False))
    connection = op.get_bind()
    workflows = sa.table("image_workflows", sa.column("id"), sa.column("instructions"), sa.column("prompt_template"))
    for row in connection.execute(sa.select(workflows.c.id, workflows.c.instructions)).all():
        connection.execute(workflows.update().where(workflows.c.id == row.id).values(
            prompt_template=_TEMPLATE_HEAD + row.instructions.strip() + _TEMPLATE_TAIL))
    op.execute("ALTER TABLE image_workflows DROP COLUMN instructions")

    op.add_column("chat_illustration_settings", sa.Column("focus", sa.JSON(none_as_null=True), server_default="[]", nullable=False))
    op.add_column("illustrations", sa.Column("focus", sa.JSON(none_as_null=True), server_default="[]", nullable=False))

    op.create_table(
        "cast_members",
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("appearance", sa.Text(), server_default="", nullable=False),
        sa.Column("reference_image", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.CheckConstraint('"order" >= 0', name=op.f("ck_cast_members_nonnegative_order")),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], name=op.f("fk_cast_members_character_id_characters"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cast_members")),
    )
    with op.batch_alter_table("cast_members") as batch:
        batch.create_index(batch.f("ix_cast_members_character_id"), ["character_id"], unique=False)
    op.create_table(
        "identity_appearances",
        sa.Column("user_identity_id", sa.String(length=36), nullable=False),
        sa.Column("appearance", sa.Text(), server_default="", nullable=False),
        sa.Column("reference_image", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_identity_id"], ["user_identities.id"],
                                name=op.f("fk_identity_appearances_user_identity_id_user_identities"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_identity_id", name=op.f("pk_identity_appearances")),
    )


def downgrade():
    op.drop_table("identity_appearances")
    with op.batch_alter_table("cast_members") as batch:
        batch.drop_index(batch.f("ix_cast_members_character_id"))
    op.drop_table("cast_members")
    op.execute("ALTER TABLE illustrations DROP COLUMN focus")
    op.execute("ALTER TABLE chat_illustration_settings DROP COLUMN focus")
    # Templates can't be turned back into instructions; old rows start with empty instructions.
    op.add_column("image_workflows", sa.Column("instructions", sa.Text(), server_default="", nullable=False))
    op.execute("ALTER TABLE image_workflows DROP COLUMN prompt_template")
