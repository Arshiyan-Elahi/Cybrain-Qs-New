"""
Structure normalizer — multi-signal inference after raw extraction.

Does not depend on fixed SOP section names (PURPOSE / SCOPE / …). Those names
may appear only as weak optional hints. Repeated page furniture is marked
non-semantic while retained for audit/provenance.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.processing.schema import NormalizedBlock, NormalizedDocument

_NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+")
_APPENDIX = re.compile(r"^\s*appendix\b", re.I)
_REVISION = re.compile(
    r"\b(revision|change\s*history|document\s*history|versionshistorie|"
    r"änderungshistorie)\b",
    re.I,
)
# Weak optional hints only — never required for structure.
_WEAK_SECTION_HINTS = re.compile(
    r"\b(purpose|scope|responsibilit|procedure|references|definitions|"
    r"zweck|geltungsbereich|verantwort|ablauf|anhang)\b",
    re.I,
)


def normalize_document(document: NormalizedDocument) -> NormalizedDocument:
    blocks = list(document.blocks)
    blocks = _mark_repeated_furniture(blocks)
    blocks = _retag_special_regions(blocks)
    blocks = _infer_heading_levels(blocks)
    blocks = _assign_heading_paths(blocks)
    blocks = _ensure_source_order(blocks)
    document.blocks = blocks
    return document


def _mark_repeated_furniture(blocks: list[NormalizedBlock]) -> list[NormalizedBlock]:
    """Detect repeated short lines across pages (headers/footers/doc-control)."""
    by_text: dict[str, list[NormalizedBlock]] = defaultdict(list)
    pages_seen: set[int] = set()
    for block in blocks:
        if block.page is not None:
            pages_seen.add(block.page)
        if block.type in ("table", "approval_signature", "revision_history"):
            continue
        text = block.text.strip()
        if not text or len(text) > 120:
            continue
        by_text[text.casefold()].append(block)

    page_count = len(pages_seen) or 1
    for _key, group in by_text.items():
        pages = {b.page for b in group if b.page is not None}
        # Same short text on 2+ pages (or majority of pages) → furniture.
        if len(pages) >= 2 or (page_count >= 3 and len(pages) >= max(2, page_count // 2)):
            for block in group:
                if block.type == "heading" and _NUMBERED.match(block.text):
                    continue
                block.type = "header_footer"
                block.semantic = False
                block.style = {**block.style, "furniture": True, "repeated": True}
                block.provenance = {**block.provenance, "furniture": True}
    return blocks


def _retag_special_regions(blocks: list[NormalizedBlock]) -> list[NormalizedBlock]:
    in_appendix = False
    in_revision = False
    for block in blocks:
        if block.type == "header_footer":
            continue
        if block.type in ("heading", "appendix"):
            if block.type == "appendix" or _APPENDIX.match(block.text):
                block.type = "appendix"
                in_appendix = True
                in_revision = False
            elif _REVISION.search(block.text):
                in_revision = True
                in_appendix = False
            else:
                # Leaving a special region when a new numbered section starts.
                if _NUMBERED.match(block.text):
                    in_appendix = False
                    in_revision = False
            # Weak hints never force a type change.
            _ = _WEAK_SECTION_HINTS.search(block.text)
            continue

        if block.type == "table" and in_revision:
            block.type = "revision_history"
            continue

        if in_appendix and block.type in ("paragraph", "list"):
            block.style = {**block.style, "region": "appendix"}
            block.provenance = {**block.provenance, "region": "appendix"}
        if in_revision and block.type in ("paragraph", "list", "table"):
            if block.type == "table":
                block.type = "revision_history"
            block.style = {**block.style, "region": "revision_history"}
    return blocks


def _infer_heading_levels(blocks: list[NormalizedBlock]) -> list[NormalizedBlock]:
    headings = [b for b in blocks if b.type in ("heading", "appendix")]
    # Prefer explicit numbering depth when present.
    for block in headings:
        match = _NUMBERED.match(block.text)
        if match:
            block.heading_level = match.group(1).count(".") + 1
        elif block.type == "appendix":
            block.heading_level = block.heading_level or 1
        elif block.heading_level is None:
            # Font-size signal from style metadata when available.
            size = block.style.get("font_size_pt")
            if isinstance(size, (int, float)) and size >= 16:
                block.heading_level = 1
            elif isinstance(size, (int, float)) and size >= 13:
                block.heading_level = 2
            else:
                block.heading_level = 2
    return blocks


def _assign_heading_paths(blocks: list[NormalizedBlock]) -> list[NormalizedBlock]:
    stack: list[tuple[int, str]] = []
    for block in blocks:
        if block.type in ("heading", "appendix"):
            level = block.heading_level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, block.text))
            block.heading_path = [title for _, title in stack]
            continue
        if block.type == "header_footer" or not block.semantic:
            block.heading_path = []
            continue
        block.heading_path = [title for _, title in stack]
    return blocks


def _ensure_source_order(blocks: list[NormalizedBlock]) -> list[NormalizedBlock]:
    blocks.sort(key=lambda b: b.order)
    # Header/footer furniture extracted from DOCX sections was appended at the
    # end; keep that audit trail but ensure unique contiguous orders.
    for index, block in enumerate(blocks):
        block.order = index
    return blocks
