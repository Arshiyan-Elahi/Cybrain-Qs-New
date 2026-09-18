"""
Format-independent normalized document structure.

Every parser (DOCX, digital PDF, OCR) emits this shape before chunking,
embeddings or CKM extraction. Source-format quirks stay in style/provenance;
callers consume a stable block model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockType = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "document_metadata",
    "header_footer",
    "approval_signature",
    "revision_history",
    "appendix",
]

QaSeverity = Literal["PASS", "WARNING", "FAILED"]
PdfKind = Literal["digital", "mixed", "scanned"]
SourceFormat = Literal["pdf", "docx"]


@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def as_dict(self) -> dict[str, float]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass
class NormalizedBlock:
    id: str
    type: BlockType
    text: str
    raw_text: str
    order: int
    page: int | None = None
    heading_level: int | None = None
    heading_path: list[str] = field(default_factory=list)
    semantic: bool = True
    bbox: BoundingBox | None = None
    style: dict[str, Any] = field(default_factory=dict)
    table: dict[str, Any] | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionDiagnostic:
    code: str
    severity: QaSeverity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionQA:
    status: QaSeverity
    diagnostics: list[ExtractionDiagnostic] = field(default_factory=list)

    def messages(self) -> list[str]:
        return [f"[{d.severity}] {d.code}: {d.message}" for d in self.diagnostics]


@dataclass
class PageInfo:
    number: int
    width: float | None = None
    height: float | None = None
    text_chars: int = 0
    has_text_layer: bool = False
    ocr_applied: bool = False
    classification: Literal["text", "image", "mixed", "empty"] = "empty"


@dataclass
class NormalizedDocument:
    metadata: dict[str, Any]
    pages: list[PageInfo]
    blocks: list[NormalizedBlock]
    warnings: list[str]
    extraction_quality: ExtractionQA
    source_format: SourceFormat
    pdf_kind: PdfKind | None = None
    ocr_used: bool = False
    parser: str = ""

    @property
    def page_count(self) -> int:
        return len(self.pages) if self.pages else int(self.metadata.get("page_count") or 0)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks if b.text)

    @property
    def is_probably_scanned(self) -> bool:
        return self.pdf_kind == "scanned"
