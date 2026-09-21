"""sop projects for blueprint mapping

Revision ID: d5e9a2b7c814
Revises: b4e8f1c2d9a0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e9a2b7c814"
down_revision: Union[str, Sequence[str], None] = "b4e8f1c2d9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sop_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("blueprint_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blueprint", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("context_option_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("additional_context", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('planning', 'blueprint_ready', 'generation_ready')",
            name="ck_sop_project_status",
        ),
    )
    op.create_index("ix_sop_projects_company_id", "sop_projects", ["company_id"])
    op.create_index("ix_sop_projects_status", "sop_projects", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sop_projects_status", table_name="sop_projects")
    op.drop_index("ix_sop_projects_company_id", table_name="sop_projects")
    op.drop_table("sop_projects")
