"""
Turn an uploaded PDF or DOCX into ordered, structure-aware blocks.

Public API stays stable for ingestion and tests. Internally this delegates to
the layout-aware pipeline (classify → extract → normalize → QA) and adapts the
normalized schema into ExtractedBlock / ExtractedDocument.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.processing.errors import UnsupportedDocumentError
from app.processing.pipeline import run_pipeline
from app.processing.schema import NormalizedBlock, NormalizedDocument

BlockKind = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "document_metadata",
    "header_footer",
    "approval_signature",
    "revision_history",
    "appendix",
    # Legacy alias retained for older fixtures / callers.
    "appendix_revision",
]


@dataclass
class ExtractedBlock:
    kind: BlockKind
    text: str
    order: int
    level: int | None = None
    page: int | None = None
    structured: dict = field(default_factory=dict)
    semantic: bool = True
    heading_path: list[str] = field(default_factory=list)
    block_id: str = ""


@dataclass
class ExtractedDocument:
    blocks: list[ExtractedBlock]
    page_count: int
    source_format: str
    warnings: list[str] = field(default_factory=list)
    is_probably_scanned: bool = False
    qa_status: Literal["PASS", "WARNING", "FAILED"] = "PASS"
    pdf_kind: str | None = None
    ocr_used: bool = False
    parser: str = ""
    normalized: NormalizedDocument | None = None

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks)


def extract(content: bytes, filename: str) -> ExtractedDocument:
    normalized = run_pipeline(content, filename)
    return to_extracted(normalized)


def to_extracted(normalized: NormalizedDocument) -> ExtractedDocument:
    blocks = [_adapt_block(block) for block in normalized.blocks]
    return ExtractedDocument(
        blocks=blocks,
        page_count=normalized.page_count,
        source_format=normalized.source_format,
        warnings=list(normalized.warnings),
        is_probably_scanned=normalized.is_probably_scanned,
        qa_status=normalized.extraction_quality.status,
        pdf_kind=normalized.pdf_kind,
        ocr_used=normalized.ocr_used,
        parser=normalized.parser,
        normalized=normalized,
    )


def _adapt_block(block: NormalizedBlock) -> ExtractedBlock:
    kind = _map_kind(block)
    structured: dict = dict(block.style)
    if block.table:
        structured["rows"] = block.table.get("rows", [])
        if block.type == "approval_signature":
            structured["tableType"] = "approval"
        elif block.type == "revision_history":
            structured["tableType"] = "revision_history"
            structured["contentType"] = "appendix_or_revision"
        else:
            structured["tableType"] = "content"
    if block.type == "appendix" or block.style.get("region") == "appendix":
        structured["contentType"] = "appendix_or_revision"
        structured["appendix"] = True
    if block.bbox:
        structured["bbox"] = block.bbox.as_dict()
    if block.provenance:
        structured["provenance"] = block.provenance
    if block.heading_path:
        structured["heading_path"] = list(block.heading_path)

    return ExtractedBlock(
        kind=kind,
        text=block.text,
        order=block.order,
        level=block.heading_level,
        page=block.page,
        structured=structured,
        semantic=block.semantic,
        heading_path=list(block.heading_path),
        block_id=block.id,
    )


def _map_kind(block: NormalizedBlock) -> BlockKind:
    if block.type == "appendix":
        return "appendix"
    if block.style.get("region") == "appendix" and block.type == "paragraph":
        return "appendix_revision"
    if block.style.get("region") == "revision_history" and block.type == "paragraph":
        return "appendix_revision"
    return block.type  # type: ignore[return-value]
