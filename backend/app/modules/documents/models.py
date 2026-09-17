import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.enums import DocumentStatus, KnowledgeTier
from app.shared.models import Base, TimestampMixin

# Fixed at the schema level. Changing it means a migration and a full
# re-embed, so it is a constant here rather than an environment read.
EMBEDDING_DIMENSIONS = 768


class Document(Base, TimestampMixin):
    """
    An uploaded source file belonging to exactly one Company.

    Immutable once ingested: re-uploading the same file produces a new row, so
    Knowledge Objects keep pointing at the version they were extracted from.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), default=DocumentStatus.UPLOADED, nullable=False, index=True
    )
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Parsing problems are surfaced, never swallowed: a partially parsed
    # document must be visibly partial.
    warnings: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    # Origin in the product: general upload, onboarding SOP, or onboarding template.
    kind: Mapped[str] = mapped_column(String(32), default="general", nullable=False, index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, TimestampMixin):
    """
    A structure-aligned slice of a document plus its embedding.

    `company_id` is denormalised onto the chunk so retrieval can filter by
    company *before* the vector search rather than after it.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        # Company and tier are the pre-filter; the index leads with them.
        Index("ix_chunks_company_tier", "company_id", "tier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(
        String(16), default=KnowledgeTier.COMPANY, nullable=False, index=True
    )

    chunk_order: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    # Which model produced the vector — a mixed index is a correctness bug, so
    # this is recorded rather than assumed.
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")

    @property
    def location(self) -> str:
        where = " > ".join(self.heading_path) if self.heading_path else "(no section)"
        if self.page_start:
            span = (
                f"p.{self.page_start}"
                if self.page_start == self.page_end
                else f"pp.{self.page_start}-{self.page_end}"
            )
            return f"{where} [{span}]"
        return where

    @property
    def section_id(self) -> str | None:
        return self.extra.get("sectionId")

    @property
    def structured_blocks(self) -> list[dict]:
        return self.extra.get("blocks", [])

    @property
    def is_semantic(self) -> bool:
        return self.extra.get("isSemantic", True)
