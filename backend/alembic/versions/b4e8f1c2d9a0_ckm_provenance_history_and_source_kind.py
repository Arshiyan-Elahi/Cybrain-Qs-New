"""ckm provenance source_kind history and nullable document

Revision ID: b4e8f1c2d9a0
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b4e8f1c2d9a0"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_objects",
        sa.Column("source_kind", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_objects",
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_objects_rejected_by_users",
        "knowledge_objects",
        "users",
        ["rejected_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_knowledge_objects_supersedes_id",
        "knowledge_objects",
        "knowledge_objects",
        ["supersedes_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_knowledge_objects_source_kind", "knowledge_objects", ["source_kind"])
    op.create_index("ix_knowledge_objects_supersedes_id", "knowledge_objects", ["supersedes_id"])

    op.execute(
        """
        UPDATE knowledge_objects
        SET source_kind = CASE
            WHEN extraction_method LIKE 'local-llm%' THEN 'ai_extracted'
            WHEN extraction_method = 'human-edit' THEN 'human_created'
            WHEN extraction_method = 'onboarding-profile' THEN 'onboarding'
            ELSE 'uploaded_document'
        END
        WHERE source_kind IS NULL
        """
    )
    op.alter_column("knowledge_objects", "source_kind", nullable=False)
    op.alter_column("knowledge_objects", "source_document_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    op.create_check_constraint(
        "ck_knowledge_source_kind",
        "knowledge_objects",
        "source_kind IN ('onboarding', 'uploaded_document', 'human_created', 'ai_extracted')",
    )
    op.create_check_constraint(
        "ck_knowledge_source_document_or_kind",
        "knowledge_objects",
        "source_document_id IS NOT NULL OR source_kind IN ('onboarding', 'human_created')",
    )
    op.create_table(
        "knowledge_object_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_objects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("payload_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_object_history_company_id", "knowledge_object_history", ["company_id"])
    op.create_index("ix_knowledge_object_history_knowledge_object_id", "knowledge_object_history", ["knowledge_object_id"])


def downgrade() -> None:
    op.drop_table("knowledge_object_history")
    op.drop_constraint("ck_knowledge_source_document_or_kind", "knowledge_objects", type_="check")
    op.drop_constraint("ck_knowledge_source_kind", "knowledge_objects", type_="check")
    op.drop_constraint("fk_knowledge_objects_supersedes_id", "knowledge_objects", type_="foreignkey")
    op.drop_constraint("fk_knowledge_objects_rejected_by_users", "knowledge_objects", type_="foreignkey")
    op.drop_index("ix_knowledge_objects_supersedes_id", table_name="knowledge_objects")
    op.drop_index("ix_knowledge_objects_source_kind", table_name="knowledge_objects")
    op.drop_column("knowledge_objects", "supersedes_id")
    op.drop_column("knowledge_objects", "rejected_at")
    op.drop_column("knowledge_objects", "rejected_by")
    op.drop_column("knowledge_objects", "source_kind")
    op.alter_column("knowledge_objects", "source_document_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
