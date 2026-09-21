import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.shared.schemas import CamelModel

GenerationStatus = Literal["grounded", "partial", "blocked"]
StructureSource = Literal[
    "verified_document_structure",
    "uploaded_sop_structure",
    "generic_fallback",
]
EvidenceKind = Literal["verified_knowledge", "source_chunk"]
GapSeverity = Literal["required", "optional"]


class SopProjectCreate(CamelModel):
    title: str = Field(min_length=1, max_length=500)
    topic: str = Field(min_length=1, max_length=2000)
    context_option_ids: list[str] = Field(default_factory=list)
    additional_context: str = Field(default="", max_length=20000)


class BlueprintEvidenceRead(CamelModel):
    kind: EvidenceKind
    id: uuid.UUID
    label: str
    type: str | None = None
    tier: str
    status: str
    similarity: float | None = None
    source_document_id: uuid.UUID | None = None
    source_document_name: str | None = None
    source_chunk_id: uuid.UUID | None = None
    source_location: str | None = None
    snippet: str | None = None
    verified_by: uuid.UUID | None = None
    verified_at: str | None = None


class BlueprintGapRead(CamelModel):
    field: str
    reason: str
    severity: GapSeverity


class BlueprintSectionRead(CamelModel):
    section_key: str
    heading: str
    objective: str
    knowledge_object_ids: list[uuid.UUID]
    source_chunk_ids: list[uuid.UUID]
    regulation_ids: list[str]
    evidence: list[BlueprintEvidenceRead]
    gaps: list[BlueprintGapRead]
    generation_status: GenerationStatus


class GenerationGuidanceRead(CamelModel):
    id: uuid.UUID
    type: str
    label: str
    tier: str
    status: str


class BlueprintSummaryRead(CamelModel):
    grounded: int
    partial: int
    blocked: int
    gap_count: int
    verified_knowledge_mapped: int
    fallback_structure: bool
    verified_pool_size: int


class SopBlueprintRead(CamelModel):
    title: str
    topic: str
    structure_source: StructureSource
    structure_source_note: str
    structure_source_document_id: uuid.UUID | None = None
    generation_guidance: list[GenerationGuidanceRead]
    unmapped_knowledge: list[BlueprintEvidenceRead]
    sections: list[BlueprintSectionRead]
    company_regulation_ids: list[str]
    summary: BlueprintSummaryRead
    retrieval_notes: list[str] = Field(default_factory=list)


class SopProjectRead(CamelModel):
    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    topic: str
    status: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    blueprint_version: int
    context_option_ids: list[str]
    additional_context: str
    blueprint: SopBlueprintRead | None = None
