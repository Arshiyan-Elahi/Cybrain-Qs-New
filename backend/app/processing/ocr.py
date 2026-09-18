"""OCR provider protocol for scanned / mixed PDF pages.

Heavy OCR engines (Docling OCR, Tesseract+layout, Azure Document Intelligence,
etc.) are intentionally not hard-wired into the default runtime. Production
deployments should register a concrete provider that returns layout-preserving
blocks with bounding boxes rather than a flat text blob.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.processing.schema import BoundingBox, NormalizedBlock


@dataclass
class OcrPageRequest:
    page_number: int
    pdf_bytes: bytes
    page_image: bytes | None = None
    width: float | None = None
    height: float | None = None


@dataclass
class OcrPageResult:
    page_number: int
    blocks: list[NormalizedBlock] = field(default_factory=list)
    engine: str = ""
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class OcrProvider(Protocol):
    """Layout-aware OCR for pages that lack a reliable text layer."""

    name: str

    def ocr_pages(self, pages: list[OcrPageRequest]) -> list[OcrPageResult]:
        """Return structured blocks with bbox/page provenance where possible."""
        ...


class NullOcrProvider:
    """Default provider: detects need for OCR but does not run an engine."""

    name = "null"

    def ocr_pages(self, pages: list[OcrPageRequest]) -> list[OcrPageResult]:
        return [
            OcrPageResult(
                page_number=page.page_number,
                blocks=[],
                engine=self.name,
                warnings=[
                    f"Page {page.page_number} requires OCR but no OCR engine is configured."
                ],
            )
            for page in pages
        ]


# Recommended production engines (not bundled):
# - Docling PdfPipelineOptions(do_ocr=True) when the Docling stack is installed
# - Tesseract / ocrmypdf with layout PDF/A output for offline air-gapped sites
# - Cloud document AI only when regulatory data-residency policy allows it
RECOMMENDED_OCR_ENGINES = (
    "docling-ocr",
    "tesseract-layout",
    "ocrmypdf",
)

_active_provider: OcrProvider = NullOcrProvider()


def get_ocr_provider() -> OcrProvider:
    return _active_provider


def set_ocr_provider(provider: OcrProvider) -> None:
    global _active_provider
    _active_provider = provider


def reset_ocr_provider() -> None:
    set_ocr_provider(NullOcrProvider())
