import uuid
from datetime import date, datetime

from pydantic import Field, field_serializer

from app.shared.schemas import CamelModel


class OnboardingProfileBase(CamelModel):
    """Questionnaire answers from the Create New Company wizard."""

    start_option_id: str = Field(min_length=1, max_length=64)
    document_path_id: str = Field(min_length=1, max_length=64)

    structure_preference_id: str = Field(default="", max_length=64)
    document_structure_notes: str = Field(default="", max_length=20000)

    tone_id: str = Field(default="", max_length=64)
    formality_id: str = Field(default="", max_length=64)
    person_id: str = Field(default="", max_length=64)
    writing_notes: str = Field(default="", max_length=20000)

    terminology_text: str = Field(default="", max_length=20000)
    prefer_existing_terms: bool = True

    departments_text: str = Field(default="", max_length=20000)
    roles_text: str = Field(default="", max_length=20000)

    processes_text: str = Field(default="", max_length=20000)
    workflow_notes: str = Field(default="", max_length=20000)

    template_preference_id: str = Field(default="", max_length=64)
    layout_notes: str = Field(default="", max_length=20000)

    forms_text: str = Field(default="", max_length=20000)
    business_rules_text: str = Field(default="", max_length=20000)
    relationships_text: str = Field(default="", max_length=20000)
    best_practices_text: str = Field(default="", max_length=20000)

    ai_assist_level_id: str = Field(default="", max_length=64)
    require_human_verification: bool = True
    quality_notes: str = Field(default="", max_length=20000)

    intended_document_names: list[str] = Field(default_factory=list)
    intended_template_names: list[str] = Field(default_factory=list)


class OnboardingProfileWrite(OnboardingProfileBase):
    pass


class OnboardingProfileRead(OnboardingProfileBase):
    company_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CompanyBase(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    industry_key: str = Field(min_length=1, max_length=64)
    location_key: str = Field(min_length=1, max_length=64)
    primary_language_key: str = Field(default="de", max_length=8)
    regulation_ids: list[str] = Field(default_factory=list)
    sop_count: int = Field(default=0, ge=0)


class CompanyCreate(CompanyBase):
    creation_request_id: uuid.UUID | None = None
    onboarding: OnboardingProfileWrite | None = None


class CompanyUpdate(CamelModel):
    """Every field optional — only what is sent gets changed."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    industry_key: str | None = Field(default=None, max_length=64)
    location_key: str | None = Field(default=None, max_length=64)
    primary_language_key: str | None = Field(default=None, max_length=8)
    regulation_ids: list[str] | None = None
    sop_count: int | None = Field(default=None, ge=0)
    onboarding: OnboardingProfileWrite | None = None


class CompanyRead(CompanyBase):
    """Response shape. Field names mirror the frontend's `Company` interface."""

    id: uuid.UUID
    creation_request_id: uuid.UUID | None = None
    onboarding: OnboardingProfileRead | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _as_iso_date(self, value: datetime) -> date:
        # The UI formats dates per locale from an ISO date string.
        return value.date()
