"""Extraction QA gate — observable PASS / WARNING / FAILED diagnostics only."""

from __future__ import annotations

from collections import Counter

from app.processing.schema import (
    ExtractionDiagnostic,
    ExtractionQA,
    NormalizedBlock,
    NormalizedDocument,
    QaSeverity,
)


def evaluate_extraction(document: NormalizedDocument) -> ExtractionQA:
    diagnostics: list[ExtractionDiagnostic] = []
    blocks = document.blocks
    semantic = [b for b in blocks if b.semantic]
    text_chars = sum(len(b.text) for b in blocks)
    pages = document.pages

    if not blocks or text_chars == 0:
        if document.pdf_kind == "scanned" or document.metadata.get("needs_ocr"):
            diagnostics.append(
                ExtractionDiagnostic(
                    code="no_text_needs_ocr",
                    severity="FAILED",
                    message="No extractable text; document needs OCR before analysis.",
                    evidence={"pdf_kind": document.pdf_kind, "page_count": document.page_count},
                )
            )
        else:
            diagnostics.append(
                ExtractionDiagnostic(
                    code="no_readable_text",
                    severity="FAILED",
                    message="The document contains no readable text.",
                    evidence={"page_count": document.page_count},
                )
            )
    else:
        diagnostics.append(
            ExtractionDiagnostic(
                code="text_availability",
                severity="PASS",
                message=f"Extracted {text_chars} characters across {len(blocks)} blocks.",
                evidence={"chars": text_chars, "blocks": len(blocks)},
            )
        )

    empty_pages = [p for p in pages if p.text_chars == 0 and not p.ocr_applied]
    if empty_pages and document.source_format == "pdf":
        ratio = len(empty_pages) / max(len(pages), 1)
        severity: QaSeverity = "FAILED" if ratio >= 0.5 and text_chars == 0 else "WARNING"
        diagnostics.append(
            ExtractionDiagnostic(
                code="empty_or_low_text_pages",
                severity=severity,
                message=f"{len(empty_pages)} page(s) have no extractable text.",
                evidence={
                    "empty_pages": [p.number for p in empty_pages],
                    "ratio": round(ratio, 3),
                },
            )
        )

    headings = [b for b in blocks if b.type == "heading"]
    if semantic and not headings:
        diagnostics.append(
            ExtractionDiagnostic(
                code="heading_hierarchy_missing",
                severity="WARNING",
                message="No headings detected; structure may be flat.",
                evidence={"semantic_blocks": len(semantic)},
            )
        )
    elif headings:
        levels = [h.heading_level or 1 for h in headings]
        # Skip levels that jump more than one step are suspicious but not fatal.
        jumps = sum(
            1
            for prev, cur in zip(levels, levels[1:])
            if cur > prev + 1
        )
        if jumps:
            diagnostics.append(
                ExtractionDiagnostic(
                    code="heading_hierarchy_jump",
                    severity="WARNING",
                    message=f"Heading level jumps detected ({jumps}).",
                    evidence={"levels_sample": levels[:20]},
                )
            )
        else:
            diagnostics.append(
                ExtractionDiagnostic(
                    code="heading_hierarchy",
                    severity="PASS",
                    message=f"Detected {len(headings)} headings with coherent levels.",
                    evidence={"heading_count": len(headings)},
                )
            )

    tables = [b for b in blocks if b.type in ("table", "revision_history", "approval_signature")]
    tables_with_cells = [b for b in tables if b.table and b.table.get("rows")]
    if tables and not tables_with_cells:
        diagnostics.append(
            ExtractionDiagnostic(
                code="table_structure_lost",
                severity="WARNING",
                message="Tables found without preserved cell structure.",
                evidence={"table_blocks": len(tables)},
            )
        )
    elif tables_with_cells:
        diagnostics.append(
            ExtractionDiagnostic(
                code="table_preservation",
                severity="PASS",
                message=f"Preserved cell structure for {len(tables_with_cells)} table(s).",
                evidence={"tables_with_cells": len(tables_with_cells)},
            )
        )

    orders = [b.order for b in blocks]
    if orders != sorted(orders):
        diagnostics.append(
            ExtractionDiagnostic(
                code="reading_order",
                severity="WARNING",
                message="Block order is not strictly ascending.",
                evidence={"orders_sample": orders[:30]},
            )
        )
    elif blocks:
        diagnostics.append(
            ExtractionDiagnostic(
                code="reading_order",
                severity="PASS",
                message="Blocks are in ascending source order.",
            )
        )

    if document.ocr_used:
        diagnostics.append(
            ExtractionDiagnostic(
                code="ocr_usage",
                severity="WARNING",
                message="OCR was applied to one or more pages.",
                evidence={"ocr_pages": [p.number for p in pages if p.ocr_applied]},
            )
        )
    elif document.pdf_kind in ("scanned", "mixed"):
        diagnostics.append(
            ExtractionDiagnostic(
                code="ocr_required_not_run",
                severity="FAILED" if document.pdf_kind == "scanned" else "WARNING",
                message="Scanned or mixed pages need OCR; no OCR engine produced text.",
                evidence={"pdf_kind": document.pdf_kind},
            )
        )

    # Suspicious structure loss: almost everything classified as paragraph.
    type_counts = Counter(b.type for b in blocks)
    if len(blocks) >= 12 and type_counts.get("paragraph", 0) / len(blocks) > 0.95:
        diagnostics.append(
            ExtractionDiagnostic(
                code="suspicious_structure_loss",
                severity="WARNING",
                message="Nearly all blocks are paragraphs; layout signals may be weak.",
                evidence=dict(type_counts),
            )
        )

    status = _rollup(diagnostics)
    return ExtractionQA(status=status, diagnostics=diagnostics)


def _rollup(diagnostics: list[ExtractionDiagnostic]) -> QaSeverity:
    if any(d.severity == "FAILED" for d in diagnostics):
        return "FAILED"
    if any(d.severity == "WARNING" for d in diagnostics):
        return "WARNING"
    return "PASS"


def attach_qa(document: NormalizedDocument) -> NormalizedDocument:
    document.extraction_quality = evaluate_extraction(document)
    for message in document.extraction_quality.messages():
        if message not in document.warnings:
            document.warnings.append(message)
    return document
