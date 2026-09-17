import uuid
from datetime import datetime

from app.shared.schemas import CamelModel



class DocumentRead(CamelModel):

    id: uuid.UUID
    company_id: uuid.UUID
    filename: str
    source_format: str
    status: str
    page_count: int
    byte_size: int
    # Parsing problems are part of the response, never hidden from the user.
    warnings: list[str]
    kind: str = "general"
    created_at: datetime


class DocumentDetail(DocumentRead):
    chunk_count: int
    semantic_chunk_count: int
    embedded_chunk_count: int


class ChunkRead(CamelModel):

    id: uuid.UUID
    chunk_order: int
    text: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    tier: str
    section_id: str | None
    structured_blocks: list[dict]
    is_semantic: bool


class CompanyStats(CamelModel):
    """Dashboard counters for one company. No AI involved."""

    company_id: uuid.UUID
    document_count: int
    processed_count: int
    needs_ocr_count: int
    failed_count: int
    chunk_count: int
    total_bytes: int
    # Present so the UI can show the CKM panel honestly while AI is off.
    ai_features_enabled: bool
    embedded_chunk_count: int
