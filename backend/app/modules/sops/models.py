import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.enums import SopProjectStatus
from app.shared.models import Base, TimestampMixin


class SopProject(Base, TimestampMixin):
    """
    Company-scoped SOP project through blueprint review.

    Approval, immutable SOP versions and generated prose are out of scope.
    """

    __tablename__ = "sop_projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planning', 'blueprint_ready', 'generation_ready')",
            name="ck_sop_project_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=SopProjectStatus.PLANNING, nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    blueprint_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blueprint: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    context_option_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    additional_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
