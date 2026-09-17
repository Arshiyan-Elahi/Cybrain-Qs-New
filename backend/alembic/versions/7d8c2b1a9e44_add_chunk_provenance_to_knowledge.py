"""add chunk provenance to knowledge objects

Revision ID: 7d8c2b1a9e44
Revises: c3c67184ff59
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7d8c2b1a9e44"
down_revision: Union[str, Sequence[str], None] = "c3c67184ff59"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_objects", sa.Column("source_chunk_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_knowledge_objects_source_chunk_id", "knowledge_objects", "document_chunks",
        ["source_chunk_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("ix_knowledge_objects_source_chunk_id", "knowledge_objects", ["source_chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_objects_source_chunk_id", table_name="knowledge_objects")
    op.drop_constraint("fk_knowledge_objects_source_chunk_id", "knowledge_objects", type_="foreignkey")
    op.drop_column("knowledge_objects", "source_chunk_id")
