"""
Layout-aware ingestion pipeline:

  upload → classify → format extract → normalize → extraction QA → (chunk)

Chunking remains a separate step so callers can inspect QA before proceeding.
"""

from __future__ import annotations

from app.processing.docx_parser import extract_docx
from app.processing.errors import UnsupportedDocumentError
from app.processing.normalizer import normalize_document
from app.processing.pdf_parser import docling_available, extract_pdf
from app.processing.qa import attach_qa
from app.processing.schema import NormalizedDocument
from app.core.logging import get_logger, log_event, logging_flags

__all__ = ["UnsupportedDocumentError", "classify_source", "run_pipeline"]

logger = get_logger("app.processing.pipeline")


def classify_source(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".docx"):
        return "docx"
    raise UnsupportedDocumentError(
        f"Unsupported file type for {filename!r}. Supported: .pdf, .docx"
    )


def run_pipeline(content: bytes, filename: str) -> NormalizedDocument:
    source = classify_source(filename)
    if logging_flags().get("log_document_processing", True):
        log_event(
            logger,
            "document_classified",
            f"Document classified as {source}",
            source_format=source,
            filename=filename,
        )
        if source == "pdf":
            if docling_available():
                log_event(logger, "docling_selected", "Docling selected for PDF")
                log_event(logger, "parser_selected", "parser=docling", parser="docling")
            else:
                log_event(logger, "pypdf_fallback", "pypdf used as PDF parser")
                log_event(logger, "parser_selected", "parser=pypdf", parser="pypdf")
        else:
            log_event(logger, "parser_selected", "parser=python-docx", parser="python-docx")

    if source == "pdf":
        raw = extract_pdf(content)
    else:
        raw = extract_docx(content)

    normalized = normalize_document(raw)
    result = attach_qa(normalized)
    if logging_flags().get("log_document_processing", True):
        log_event(
            logger,
            "normalization_completed",
            "Normalization completed",
            block_count=len(result.blocks),
            qa_status=result.extraction_quality.status,
            parser=result.parser,
        )
    return result
