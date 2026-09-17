import uuid
from datetime import datetime

from app.shared.schemas import CamelModel
from pydantic import Field


class KnowledgeObjectUpdate(CamelModel):
    label: str = Field(min_length=1, max_length=500)


class KnowledgeExtractionResult(CamelModel):
    created: int
    skipped_chunks: int
    status: str = "completed"


class KnowledgeObjectRead(CamelModel):
    id: uuid.UUID
    company_id: uuid.UUID
    type: str
    tier: str
    status: str
    label: str
    payload: dict
    source_document_id: uuid.UUID
    source_document_name: str
    source_chunk_id: uuid.UUID | None
    source_location: str
    extraction_method: str
    model_name: str | None
    model_provider: str | None
    extracted_at: datetime
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    version: int
