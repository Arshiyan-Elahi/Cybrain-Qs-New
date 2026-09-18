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
