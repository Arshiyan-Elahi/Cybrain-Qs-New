"""company onboarding profile and document kind

Revision ID: a1b2c3d4e5f6
Revises: 7d8c2b1a9e44
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7d8c2b1a9e44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("creation_request_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_companies_creation_request_id",
        "companies",
        ["creation_request_id"],
        unique=True,
    )

    op.create_table(
        "company_onboarding_profiles",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("start_option_id", sa.String(length=64), nullable=False),
        sa.Column("document_path_id", sa.String(length=64), nullable=False),
        sa.Column("structure_preference_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("document_structure_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("tone_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("formality_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("person_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("writing_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("terminology_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("prefer_existing_terms", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("departments_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("roles_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("processes_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("workflow_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("template_preference_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("layout_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("forms_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("business_rules_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("relationships_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("best_practices_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("ai_assist_level_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "require_human_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("quality_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "intended_document_names",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "intended_template_names",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("company_id"),
    )

    op.add_column(
        "documents",
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="general"),
    )
    op.create_index("ix_documents_kind", "documents", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_documents_kind", table_name="documents")
    op.drop_column("documents", "kind")
    op.drop_table("company_onboarding_profiles")
    op.drop_index("ix_companies_creation_request_id", table_name="companies")
    op.drop_column("companies", "creation_request_id")
