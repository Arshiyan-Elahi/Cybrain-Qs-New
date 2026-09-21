import uuid
from datetime import datetime

from pydantic import Field

from app.shared.schemas import CamelModel


class KnowledgeObjectUpdate(CamelModel):
    label: str = Field(min_length=1, max_length=500)


class KnowledgeExtractionResult(CamelModel):
    created: int
    skipped_chunks: int
    status: str = "completed"


class KnowledgeOnboardingResult(CamelModel):
    created: int


class KnowledgeObjectRead(CamelModel):
    id: uuid.UUID
    company_id: uuid.UUID
    type: str
    tier: str
    status: str
    label: str
    payload: dict
    source_kind: str
    source_document_id: uuid.UUID | None
    source_document_name: str
    source_chunk_id: uuid.UUID | None
    source_location: str
    extraction_method: str
    model_name: str | None
    model_provider: str | None
    extracted_at: datetime
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    rejected_by: uuid.UUID | None = None
    rejected_at: datetime | None = None
    supersedes_id: uuid.UUID | None = None
    version: int


class KnowledgeHistoryRead(CamelModel):
    id: uuid.UUID
    knowledge_object_id: uuid.UUID
    action: str
    actor_id: uuid.UUID | None
    label: str
    status: str
    source_kind: str
    version: int
    evidence_snapshot: list
    payload_snapshot: dict
    detail: str | None
    created_at: datetime


class RetrievalPreviewRequest(CamelModel):
    query: str = Field(min_length=1, max_length=2000)
    knowledge_limit: int = Field(default=20, ge=1, le=50)
    chunk_limit: int = Field(default=8, ge=1, le=20)


class CompanyProfileContextRead(CamelModel):
    id: uuid.UUID
    name: str
    industry_key: str
    location_key: str
    primary_language_key: str


class RegulatoryProfileRead(CamelModel):
    regulation_ids: list[str]


class OnboardingContextRead(CamelModel):
    tone_id: str
    formality_id: str
    person_id: str
    prefer_existing_terms: bool
    require_human_verification: bool


class KnowledgeCitationRead(CamelModel):
    source_kind: str
    source_document_id: uuid.UUID | None
    source_document_name: str
    source_chunk_id: uuid.UUID | None
    source_location: str
    evidence: list
    extraction_method: str
    model_name: str | None
    model_provider: str | None
    verified_by: uuid.UUID | None
    verified_at: str | None


class RetrievedKnowledgeRead(CamelModel):
    id: uuid.UUID
    type: str
    label: str
    payload: dict
    tier: str
    version: int
    status: str
    similarity: float
    citation: KnowledgeCitationRead


class KnowledgeGroupRead(CamelModel):
    type: str
    items: list[RetrievedKnowledgeRead]


class RetrievedChunkRead(CamelModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    text: str
    tier: str
    location: str
    heading_path: list[str]
    similarity: float


class RetrievalMetadataRead(CamelModel):
    query: str
    mode: str
    knowledge_ranker: str
    embedding_model: str
    embedding_dimensions: int
    verified_pool_size: int
    knowledge_returned: int
    chunk_returned: int
    latency_ms: int


class GenerationContextRead(CamelModel):
    query: str
    company: CompanyProfileContextRead
    regulatory_profile: RegulatoryProfileRead
    onboarding: OnboardingContextRead | None
    knowledge: list[KnowledgeGroupRead]
    source_chunks: list[RetrievedChunkRead]
    metadata: RetrievalMetadataRead
    notes: list[str]
