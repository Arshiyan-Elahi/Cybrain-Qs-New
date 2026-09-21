"""Deterministic terminology matching and section ranking for CKM extraction."""

from __future__ import annotations

import re
from typing import Protocol

# Hyphenated controlled-document identifiers (SOP-QA-003, SOP-GCP-010, SOP-HR-001).
DOCUMENT_ID_RE = re.compile(
    r"\b[A-Z]{2,}[A-Z0-9]*-(?:[A-Z]{2,}[A-Z0-9]*)(?:-[A-Z0-9]+)+\b",
    re.IGNORECASE,
)

# Short forms must not sit inside a hyphenated token (SOP-QA-003, OJT-form still
# matches OJT only when not glued as PREFIX-ABBREV-NUMBER; OJT-form is one hyphen).
_SHORT_BOUND = r"(?<![\w-])(?:{alts})(?![\w-])"

TERM_SPECS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "Standard Operating Procedure (SOP)",
        (r"Standard Operating Procedures?",),
        (r"SOPs?",),
    ),
    (
        "Work Instruction (WI)",
        (r"Work Instructions?",),
        (r"WIs?",),
    ),
    (
        "Quality Assurance (QA)",
        (r"Quality Assurance",),
        (r"QA",),
    ),
    (
        "Good Manufacturing Practice (GMP)",
        (r"Good Manufacturing Practices?",),
        (r"GMP",),
    ),
    (
        "Good Clinical Practice (GCP)",
        (r"Good Clinical Practices?",),
        (r"GCP",),
    ),
    (
        "Quality Management System (QMS)",
        (r"Quality Management Systems?",),
        (r"QMS",),
    ),
    (
        "On-the-Job Training (OJT)",
        (r"On-the-Job Training", r"On the Job Training"),
        (r"OJT",),
    ),
)

_DEF_KEYS = ("definition", "abbreviation", "glossary", "terminology")
_ROLE_KEYS = ("responsibilit",)
_PROC_KEYS = ("procedure", "on-the-job", "on the job")
_GENERAL_KEYS = ("purpose", "scope", "general")
_REF_KEYS = ("reference",)


class _ChunkLike(Protocol):
    heading_path: list[str]
    text: str
    chunk_order: int

    @property
    def is_semantic(self) -> bool: ...


def mask_document_ids(text: str) -> str:
    """Replace structured document IDs so embedded abbreviations cannot match."""
    return DOCUMENT_ID_RE.sub(" ", text)


def compile_term_pattern(long_forms: tuple[str, ...], short_forms: tuple[str, ...]) -> re.Pattern[str]:
    parts = [rf"(?:{form})" for form in long_forms]
    if short_forms:
        parts.append(_SHORT_BOUND.format(alts="|".join(short_forms)))
    return re.compile("|".join(parts), re.IGNORECASE)


TERM_PATTERNS: dict[str, re.Pattern[str]] = {
    label: compile_term_pattern(long_forms, short_forms)
    for label, long_forms, short_forms in TERM_SPECS
}


def occurrence_count(text: str, pattern: re.Pattern[str]) -> int:
    return len(pattern.findall(mask_document_ids(text)))


def heading_priority(heading_path: list[str]) -> int:
    """Lower is better. Definitions first; REFERENCES last for terminology."""
    blob = " / ".join(heading_path).casefold()
    if any(key in blob for key in _DEF_KEYS):
        return 0
    if any(key in blob for key in _ROLE_KEYS):
        return 1
    if any(key in blob for key in _PROC_KEYS):
        return 2
    if any(key in blob for key in _GENERAL_KEYS):
        return 4
    if any(key in blob for key in _REF_KEYS):
        return 20
    return 8


def _definition_bonus(text: str, pattern: re.Pattern[str]) -> int:
    """Prefer abbreviation-table / 'X = expanded form' lines."""
    masked = mask_document_ids(text)
    if not pattern.search(masked):
        return 0
    if re.search(r"\b(?:means|is defined as)\b", masked, re.IGNORECASE):
        return 1
    if re.search(r"\b[A-Z]{2,5}\s*[=:–—-]\s*[A-Z][A-Za-z]", masked):
        return 1
    if re.search(r"\b[A-Z]{2,5}\t+[A-Z]", masked):
        return 1
    return 0


def select_terminology_chunk(
    chunks: list[_ChunkLike], pattern: re.Pattern[str]
) -> _ChunkLike | None:
    """Pick the best defining/semantic chunk; never first-match-in-document-order."""
    scored: list[tuple[int, int, int, _ChunkLike]] = []
    for chunk in chunks:
        if not chunk.heading_path:
            continue
        masked = mask_document_ids(chunk.text)
        if not pattern.search(masked):
            continue
        rank = heading_priority(list(chunk.heading_path))
        rank -= _definition_bonus(chunk.text, pattern)
        semantic_penalty = 0 if getattr(chunk, "is_semantic", True) else 5
        scored.append((rank + semantic_penalty, chunk.chunk_order, rank, chunk))
    if not scored:
        return None
    scored.sort(key=lambda row: (row[0], row[1]))
    return scored[0][3]
