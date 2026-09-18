import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.enums import KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier
from app.shared.models import Base, TimestampMixin


class KnowledgeObject(Base, TimestampMixin):
    """
    The atomic unit of the Company Knowledge Model.

    Invariants:
    1. Automatic output enters as `proposed`; verified requires verifier + time.
    2. Provenance is mandatory via `source_kind` plus location/method; document
       FK is required except for onboarding and human-created rows.
    3. `company_id` and `tier` are columns so isolation/tier never rely on JSON.
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
        CheckConstraint(
            "source_kind IN ('onboarding', 'uploaded_document', 'human_created', 'ai_extracted')",
            name="ck_knowledge_source_kind",
        ),
        CheckConstraint(
            "source_document_id IS NOT NULL OR source_kind IN ('onboarding', 'human_created')",
            name="ck_knowledge_source_document_or_kind",
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
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # --- Provenance --------------------------------------------------------
    source_kind: Mapped[str] = mapped_column(
        String(32), default=KnowledgeSourceKind.UPLOADED_DOCUMENT, nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    source_location: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_objects.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class KnowledgeObjectHistory(Base, TimestampMixin):
    """Append-only audit trail for CKM review and revision actions."""

    __tablename__ = "knowledge_object_history"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    knowledge_object_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_snapshot: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    payload_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
