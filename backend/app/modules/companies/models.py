import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TimestampMixin


class Company(Base, TimestampMixin):
    """
    A client organisation and the isolation boundary for all tenant data.

    Language-dependent fields are stored as i18n keys, matching how the frontend
    already models them, so one row serves both English and German.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    industry_key: Mapped[str] = mapped_column(String(64), nullable=False)
    location_key: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_language_key: Mapped[str] = mapped_column(String(8), nullable=False, default="de")

    # Number of SOP documents analysed for this CKM. Becomes a derived count
    # once the documents table exists; kept as a column for now.
    sop_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Client-generated idempotency key for create-from-onboarding retries.
    creation_request_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), unique=True, nullable=True, index=True
    )

    regulations: Mapped[list["CompanyRegulation"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyRegulation.position",
        lazy="selectin",
    )
    user_access: Mapped[list["UserCompanyAccess"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    onboarding_profile: Mapped["CompanyOnboardingProfile | None"] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @property
    def regulation_ids(self) -> list[str]:
        return [entry.regulation_id for entry in self.regulations]

    @property
    def onboarding(self) -> "CompanyOnboardingProfile | None":
        return self.onboarding_profile


class CompanyRegulation(Base):
    """
    A regulatory framework that binds a company, as an ordered join row.

    A join table rather than a JSONB array because regulations are filtered on
    ("which companies are bound by EU GMP?") — see the postgres-database skill.
    """

    __tablename__ = "company_regulations"
    __table_args__ = (
        UniqueConstraint("company_id", "regulation_id", name="uq_company_regulation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    regulation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="regulations")


class CompanyOnboardingProfile(Base, TimestampMixin):
    """
    Answers from the 15-step Create New Company wizard.

    Identity fields live on `companies`; this row holds path choices and the
    questionnaire so nothing the user typed is discarded on create.
    """

    __tablename__ = "company_onboarding_profiles"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )

    start_option_id: Mapped[str] = mapped_column(String(64), nullable=False)
    document_path_id: Mapped[str] = mapped_column(String(64), nullable=False)

    structure_preference_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    document_structure_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    tone_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    formality_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    person_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    writing_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    terminology_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prefer_existing_terms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    departments_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    roles_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    processes_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workflow_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    template_preference_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    layout_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    forms_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_rules_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    relationships_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    best_practices_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    ai_assist_level_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    require_human_verification: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quality_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Filenames selected at finish time (actual bytes live in documents).
    intended_document_names: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    intended_template_names: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )

    company: Mapped["Company"] = relationship(back_populates="onboarding_profile")

