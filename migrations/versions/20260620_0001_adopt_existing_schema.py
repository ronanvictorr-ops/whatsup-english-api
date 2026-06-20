"""Adopt the existing WINGO schema under Alembic management.

Revision ID: 20260620_0001
Revises:
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models import Base


revision: str = "20260620_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_COLUMNS = {
    "students": (
        sa.Column("current_lesson", sa.Integer(), server_default="1"),
        sa.Column("onboarding_notes", sa.Text(), server_default="[]"),
        sa.Column("interests", sa.Text(), server_default=""),
        sa.Column("lesson_stage", sa.String(), server_default="context_question"),
        sa.Column("engagement_minutes", sa.Integer(), server_default="0"),
        sa.Column("messages_in_current_lesson", sa.Integer(), server_default="0"),
        sa.Column("last_lesson_date", sa.String()),
        sa.Column("last_weekly_report_week", sa.String()),
        sa.Column("canonical_state", sa.String()),
    ),
    "processed_webhook_messages": (
        sa.Column("status", sa.String(), server_default="processing"),
        sa.Column("attempts", sa.Integer(), server_default="1"),
        sa.Column("last_error", sa.Text()),
        sa.Column("completed_at", sa.DateTime()),
    ),
    "lesson_sessions": (
        sa.Column("feedback_rating", sa.Integer()),
        sa.Column("feedback_text", sa.Text()),
        sa.Column("teacher_audio_sent", sa.String(), server_default="No"),
        sa.Column("student_audio_requested", sa.String(), server_default="No"),
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    # New installations receive the full model schema. Existing installations
    # keep their data and only receive tables that did not exist yet.
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    for table_name, columns in LEGACY_COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column in columns:
            if column.name not in existing_columns:
                op.add_column(table_name, column)


def downgrade() -> None:
    # This baseline adopts databases that predate Alembic. Dropping their
    # original tables would destroy production data, so the adoption itself is
    # intentionally non-destructive. Later revisions provide normal rollbacks.
    pass
