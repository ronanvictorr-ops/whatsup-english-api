"""Add relationship memory notes.

Revision ID: 20260625_0002
Revises: 20260620_0001
Create Date: 2026-06-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_0002"
down_revision: Union[str, None] = "20260620_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "personal_notes" not in inspector.get_table_names():
        op.create_table(
            "personal_notes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("source_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("personal_notes")
    }
    if op.f("ix_personal_notes_id") not in existing_indexes:
        op.create_index(
            op.f("ix_personal_notes_id"),
            "personal_notes",
            ["id"],
            unique=False,
        )
    if op.f("ix_personal_notes_student_id") not in existing_indexes:
        op.create_index(
            op.f("ix_personal_notes_student_id"),
            "personal_notes",
            ["student_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_personal_notes_student_id"), table_name="personal_notes")
    op.drop_index(op.f("ix_personal_notes_id"), table_name="personal_notes")
    op.drop_table("personal_notes")
