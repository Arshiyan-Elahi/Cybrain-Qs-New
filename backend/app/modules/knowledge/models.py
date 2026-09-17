import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.enums import KnowledgeStatus, KnowledgeTier
from app.shared.models import Base, TimestampMixin


class KnowledgeObject(Base, TimestampMixin):
    """
    The atomic unit of the Company Knowledge Model.

    Three invariants are enforced here rather than left to application code:

    1. Anything a model produces is `proposed`. Reaching `verified` requires
       `verified_by` and `verified_at`, checked by the database.
    2. Provenance is mandatory: source document, location and extraction method
       are NOT NULL, so an unattributable fact cannot be stored.
    3. `company_id` and `tier` are columns, so retrieval filters on them before
       any vector search and never merges tiers silently.
    """

    __tablename__ = "knowledge_objects"
    __table_args__ = (
        CheckConstraint(
            "status <> 'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_verified_requires_verifier",
        ),
        CheckConstraint(
            "tier IN ('company', 'industry', 'global')", name="ck_knowledge_tier"
        ),
        CheckConstraint(
            "status IN ('proposed', 'verified', 'rejected', 'superseded')",
            name="ck_knowledge_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(
        String(16), default=KnowledgeTier.COMPANY, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=KnowledgeStatus.PROPOSED, nullable=False, index=True
    )

    label: Mapped[str] = mapped_column(String(500), nullable=False)
    # Type-specific body; shape varies by `type`, so JSONB rather than columns.
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # --- Provenance (mandatory) -------------------------------------------
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,  # nullable only for legacy objects created before chunk provenance existed
    )
    source_location: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- Human verification ------------------------------------------------
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
