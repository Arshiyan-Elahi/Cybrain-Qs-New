"""
PDF extraction: Docling preferred when installed, pypdf as structured fallback.

Also classifies digital / mixed / scanned pages and invokes the OCR provider
only for pages that lack a reliable text layer.
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from typing import Any

from app.processing.errors import UnsupportedDocumentError
from app.processing.ocr import OcrPageRequest, get_ocr_provider
from app.processing.schema import (
    BoundingBox,
    ExtractionQA,
    NormalizedBlock,
    NormalizedDocument,
    PageInfo,
    PdfKind,
)

logger = logging.getLogger(__name__)

_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_LIST_ITEM = re.compile(r"^\s*(?:[-•*•]|\(?[a-z0-9]{1,3}[.)])\s+\S")
_MIN_TEXT_CHARS = 40  # below this, treat the page text layer as unreliable


def classify_pdf_pages(content: bytes) -> tuple[list[PageInfo], PdfKind]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
    except (PdfReadError, OSError, ValueError) as exc:
        raise UnsupportedDocumentError(f"Could not read PDF: {exc}") from exc

    pages: list[PageInfo] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            raw = ""
        chars = len(raw.strip())
        box = page.mediabox
        width = float(box.width) if box else None
        height = float(box.height) if box else None
        has_text = chars >= _MIN_TEXT_CHARS
        if chars == 0:
            classification = "empty"
        elif has_text:
            classification = "text"
        else:
            classification = "mixed"
        pages.append(
            PageInfo(
                number=index,
                width=width,
                height=height,
                text_chars=chars,
                has_text_layer=has_text,
                classification=classification,  # type: ignore[arg-type]
            )
        )

    if not pages:
        return pages, "scanned"
    text_pages = sum(1 for p in pages if p.has_text_layer)
    emptyish = sum(1 for p in pages if not p.has_text_layer)
    if text_pages == 0:
        kind: PdfKind = "scanned"
    elif emptyish == 0:
        kind = "digital"
    else:
        kind = "mixed"
    return pages, kind


def extract_pdf(content: bytes) -> NormalizedDocument:
    pages, pdf_kind = classify_pdf_pages(content)

    docling_doc = _try_docling(content, pages, pdf_kind)
    if docling_doc is not None:
        return _maybe_ocr(docling_doc, content)

    return _maybe_ocr(_extract_pypdf(content, pages, pdf_kind), content)


def _maybe_ocr(document: NormalizedDocument, content: bytes) -> NormalizedDocument:
    need = [
        p
        for p in document.pages
        if not p.has_text_layer or p.classification in ("empty", "image", "mixed")
    ]
    # Only OCR pages that truly lack reliable text and produced no blocks.
    pages_with_blocks = {b.page for b in document.blocks if b.page is not None}
    ocr_targets = [
        p for p in need if p.number not in pages_with_blocks or p.text_chars < _MIN_TEXT_CHARS
    ]
    if not ocr_targets:
        return document

    provider = get_ocr_provider()
    requests = [
        OcrPageRequest(
            page_number=p.number,
            pdf_bytes=content,
            width=p.width,
            height=p.height,
        )
        for p in ocr_targets
    ]
    results = provider.ocr_pages(requests)
    order = max((b.order for b in document.blocks), default=-1) + 1
    ocr_applied = False
    for result in results:
        for warning in result.warnings:
            if warning not in document.warnings:
                document.warnings.append(warning)
        if not result.blocks:
            continue
        ocr_applied = True
        for page in document.pages:
            if page.number == result.page_number:
                page.ocr_applied = True
                page.has_text_layer = True
                page.text_chars = sum(len(b.text) for b in result.blocks)
                page.classification = "text"
        for block in result.blocks:
            block.order = order
            block.provenance = {
                **block.provenance,
                "ocr_engine": result.engine or provider.name,
            }
            document.blocks.append(block)
            order += 1

    document.blocks.sort(key=lambda b: (b.page or 0, b.order))
    for index, block in enumerate(document.blocks):
        block.order = index
    document.ocr_used = ocr_applied or document.ocr_used

    # Reclassify overall kind after OCR.
    if document.pages:
        if all(p.has_text_layer or p.ocr_applied for p in document.pages):
            if document.pdf_kind == "scanned" and ocr_applied:
                document.pdf_kind = "digital"
        elif any(p.has_text_layer or p.ocr_applied for p in document.pages):
            document.pdf_kind = "mixed"
    return document


def _try_docling(
    content: bytes, pages: list[PageInfo], pdf_kind: PdfKind
) -> NormalizedDocument | None:
    try:
        from docling.datamodel.base_models import DocumentStream, InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError:
        logger.info("Docling not installed; using pypdf PDF extraction.")
        return None

    # For scanned PDFs without a configured OCR path inside Docling options,
    # still attempt conversion; empty results fall through QA as needs_ocr.
    try:
        pipeline = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
            },
        )
        stream = DocumentStream(name="document.pdf", stream=io.BytesIO(content))
        result = converter.convert(stream)
        doc = result.document
    except Exception as exc:  # noqa: BLE001
        logger.warning("Docling PDF conversion failed; falling back to pypdf: %s", exc)
        return None

    blocks: list[NormalizedBlock] = []
    order = 0
    try:
        for item, level in doc.iterate_items():
            label = str(getattr(item, "label", "") or "").lower()
            text = (getattr(item, "text", None) or "").strip()
            page_no = _docling_page(item)
            bbox = _docling_bbox(item)

            if "table" in label:
                rows = _docling_table_rows(item, doc)
                if not rows:
                    continue
                joined = "\n".join(" | ".join(r) for r in rows)
                blocks.append(
                    NormalizedBlock(
                        id=_bid(),
                        type="table",
                        text=joined,
                        raw_text=joined,
                        order=order,
                        page=page_no,
                        bbox=bbox,
                        table={"rows": rows},
                        provenance={"parser": "docling", "label": label},
                    )
                )
                order += 1
                continue

            if not text:
                continue

            if any(tok in label for tok in ("title", "section_header", "heading")):
                block_type = "heading"
                heading_level = max(int(level or 1), 1)
            elif "list" in label:
                block_type = "list"
                heading_level = None
            elif any(tok in label for tok in ("page_header", "page_footer", "footer", "header")):
                block_type = "header_footer"
                heading_level = None
            else:
                block_type = "paragraph"
                heading_level = None

            blocks.append(
                NormalizedBlock(
                    id=_bid(),
                    type=block_type,  # type: ignore[arg-type]
                    text=text,
                    raw_text=text,
                    order=order,
                    page=page_no,
                    heading_level=heading_level,
                    semantic=block_type != "header_footer",
                    bbox=bbox,
                    style={"docling_label": label, "docling_level": level},
                    provenance={"parser": "docling"},
                )
            )
            order += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("Docling iteration failed; falling back to pypdf: %s", exc)
        return None

    if not blocks and pdf_kind != "scanned":
        return None

    # Refresh page text stats from blocks when Docling succeeded.
    enriched = list(pages)
    by_page: dict[int, int] = {}
    for block in blocks:
        if block.page:
            by_page[block.page] = by_page.get(block.page, 0) + len(block.text)
    for page in enriched:
        if page.number in by_page:
            page.text_chars = max(page.text_chars, by_page[page.number])
            page.has_text_layer = page.text_chars >= _MIN_TEXT_CHARS
            if page.has_text_layer:
                page.classification = "text"

    return NormalizedDocument(
        metadata={"page_count": len(enriched), "source_format": "pdf", "parser": "docling"},
        pages=enriched,
        blocks=blocks,
        warnings=[],
        extraction_quality=ExtractionQA(status="PASS", diagnostics=[]),
        source_format="pdf",
        pdf_kind=pdf_kind,
        parser="docling",
    )


def _extract_pypdf(
    content: bytes, pages: list[PageInfo], pdf_kind: PdfKind
) -> NormalizedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
    except (PdfReadError, OSError, ValueError) as exc:
        raise UnsupportedDocumentError(f"Could not read PDF: {exc}") from exc

    blocks: list[NormalizedBlock] = []
    warnings: list[str] = []
    order = 0

    for page_info, page in zip(pages, reader.pages, strict=False):
        page_number = page_info.number
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Page {page_number} could not be parsed: {exc}")
            continue

        if not raw.strip():
            warnings.append(
                f"Page {page_number} has no extractable text (likely scanned)."
            )
            continue

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            kind, level = _classify_line(stripped, line)
            blocks.append(
                NormalizedBlock(
                    id=_bid(),
                    type=kind,  # type: ignore[arg-type]
                    text=stripped,
                    raw_text=line,
                    order=order,
                    page=page_number,
                    heading_level=level,
                    provenance={"parser": "pypdf"},
                )
            )
            order += 1

    if pdf_kind == "scanned":
        warnings.append(
            "Most pages contain no reliable text layer. This document needs OCR "
            "before it can be analysed."
        )

    return NormalizedDocument(
        metadata={
            "page_count": len(pages),
            "source_format": "pdf",
            "parser": "pypdf",
            "needs_ocr": pdf_kind == "scanned",
        },
        pages=pages,
        blocks=blocks,
        warnings=warnings,
        extraction_quality=ExtractionQA(status="PASS", diagnostics=[]),
        source_format="pdf",
        pdf_kind=pdf_kind,
        parser="pypdf",
    )


def _classify_line(stripped: str, original: str) -> tuple[str, int | None]:
    match = _NUMBERED_HEADING.match(stripped)
    if match and len(stripped) <= 120:
        return "heading", match.group(1).count(".") + 1
    if _LIST_ITEM.match(original):
        return "list", None
    if 0 < len(stripped) <= 80 and not stripped.endswith((".", ":", ";", ",")):
        letters = [c for c in stripped if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            return "heading", 1
    return "paragraph", None


def _docling_page(item: Any) -> int | None:
    prov = getattr(item, "prov", None) or []
    if prov:
        page = getattr(prov[0], "page_no", None)
        if page is not None:
            return int(page)
    return None


def _docling_bbox(item: Any) -> BoundingBox | None:
    prov = getattr(item, "prov", None) or []
    if not prov:
        return None
    bbox = getattr(prov[0], "bbox", None)
    if bbox is None:
        return None
    try:
        return BoundingBox(
            x0=float(bbox.l),
            y0=float(bbox.t),
            x1=float(bbox.r),
            y1=float(bbox.b),
        )
    except Exception:  # noqa: BLE001
        return None


def _docling_table_rows(item: Any, doc: Any) -> list[list[str]]:
    try:
        frame = item.export_to_dataframe(doc=doc)
        return [[str(c) for c in row] for row in frame.values.tolist()]
    except Exception:  # noqa: BLE001
        text = (getattr(item, "text", None) or "").strip()
        if not text:
            return []
        return [[cell.strip() for cell in line.split("|")] for line in text.splitlines()]


def _bid() -> str:
    return uuid.uuid4().hex[:12]


# Optional convenience for callers that want a temp-file Docling path.
def docling_available() -> bool:
    try:
        import docling  # noqa: F401

        return True
    except ImportError:
        return False
