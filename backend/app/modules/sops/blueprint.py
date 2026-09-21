"""Deterministic SOP blueprint: company structure + verified CKM mapping.

LLM is not used to invent company facts. Section objectives are templates over
mapped labels and explicit gaps. Semantic similarity only ranks existing items.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.llm.embedding_profile import cosine_similarity
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.generation_context import (
    GenerationContextPackage,
    RetrievedKnowledge,
)
from app.modules.knowledge.models import KnowledgeObject
from app.modules.knowledge.retrieval import RetrievedChunk
from app.shared.enums import DocumentKind, KnowledgeStatus

MIN_SECTION_SIMILARITY = 0.30
SNIPPET_CHARS = 280

GENERIC_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("purpose", "PURPOSE", "purpose"),
    ("references", "REFERENCES", "references"),
    ("responsibilities", "RESPONSIBILITIES", "responsibilities"),
    ("sop_training_and_intended_users", "SOP TRAINING AND INTENDED USERS", "training_users"),
    ("definition_and_abbreviations", "DEFINITION AND ABBREVIATIONS", "definitions"),
    ("general", "GENERAL", "procedure"),
    ("procedure", "PROCEDURE", "procedure"),
    ("records", "RECORDS", "records"),
    ("appendices", "APPENDICES", "appendices"),
    ("sop_changes", "SOP CHANGES", "changes"),
)

REQUIRED_FAMILIES = frozenset({"purpose", "responsibilities", "procedure", "records"})

TYPE_FAMILIES: dict[str, tuple[str, ...]] = {
    "terminology": ("definitions",),
    "role": ("responsibilities",),
    "responsibility": ("responsibilities",),
    "workflow": ("procedure",),
    "process": ("procedure",),
    "business_rule": ("procedure", "purpose"),
    "regulation": ("references",),
    "form_or_record": ("records",),
    "relationship": ("procedure", "responsibilities"),
    "best_practice": ("procedure",),
}

GUIDANCE_TYPES = frozenset({"writing_style", "ai_preference"})
STRUCTURE_TYPE = "document_structure"

FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("purpose", ("purpose", "ziel", "scope of")),
    ("references", ("reference", "referenz", "applicable document")),
    ("responsibilities", ("responsib", "verantwort", "role")),
    ("training_users", ("intended user", "sop training", "schulung und")),
    ("definitions", ("definition", "abbreviation", "glossary", "terminology")),
    ("procedure", ("procedure", "prozess", "general", "allgemein")),
    ("records", ("record", "form", "dokumentation")),
    ("appendices", ("appendix", "appendices", "anhang")),
    ("changes", ("change", "revision histor", "änderung")),
)


def build_blueprint(
    *,
    db: Session,
    company_id: uuid.UUID,
    title: str,
    topic: str,
    package: GenerationContextPackage,
    trusted: list[KnowledgeObject],
    embed_pairs: list[tuple[str, list[float]]] | None = None,
) -> dict[str, Any]:
    if any(item.status != KnowledgeStatus.VERIFIED.value and str(item.status) != "verified" for item in trusted):
        trusted = [item for item in trusted if str(item.status) == KnowledgeStatus.VERIFIED.value]

    sections_meta, structure_source, structure_note, structure_document_id = _resolve_structure(
        db, company_id, trusted, package.source_chunks
    )
    ranked = {item.id: item for _kind, group in package.knowledge for item in group}
    name_by_doc: dict[uuid.UUID | None, str] = {}
    for item in ranked.values():
        if item.citation.source_document_id:
            name_by_doc[item.citation.source_document_id] = item.citation.source_document_name
    for hit in package.source_chunks:
        name_by_doc[hit.document_id] = hit.document_filename

    guidance: list[dict[str, Any]] = []
    content_items: list[tuple[KnowledgeObject, RetrievedKnowledge | None]] = []
    for item in trusted:
        if item.type in GUIDANCE_TYPES:
            guidance.append(
                {
                    "id": item.id,
                    "type": item.type,
                    "label": item.label,
                    "tier": str(item.tier),
                    "status": str(item.status),
                }
            )
            continue
        if item.type == STRUCTURE_TYPE:
            continue
        content_items.append((item, ranked.get(item.id)))

    mapped_ids: set[uuid.UUID] = set()
    section_kos: dict[str, list[tuple[KnowledgeObject, RetrievedKnowledge | None, float]]] = {
        key: [] for key, _heading, _family in sections_meta
    }
    for item, retrieved in content_items:
        key, score = _assign_section(item, retrieved, sections_meta, topic, embed_pairs)
        if key is None:
            continue
        section_kos[key].append((item, retrieved, score))
        mapped_ids.add(item.id)

    chunk_by_section: dict[str, list[RetrievedChunk]] = {key: [] for key, _h, _f in sections_meta}
    used_chunk_ids: set[uuid.UUID] = set()
    for hit in package.source_chunks:
        key = _section_for_heading(hit.heading_path[0] if hit.heading_path else hit.location, sections_meta)
        if key is None:
            key = _closest_section_key(hit.location or hit.text[:80], sections_meta, embed_pairs)
        if key is None:
            continue
        chunk_by_section[key].append(hit)
        used_chunk_ids.add(hit.chunk_id)

    unmapped = [
        _knowledge_evidence(item, ranked.get(item.id), name_by_doc)
        for item, retrieved in content_items
        if item.id not in mapped_ids
    ]

    built_sections: list[dict[str, Any]] = []
    for key, heading, family in sections_meta:
        kos = section_kos.get(key, [])
        hits = chunk_by_section.get(key, [])
        evidence = [
            _knowledge_evidence(item, retrieved, name_by_doc, similarity=score)
            for item, retrieved, score in kos
        ]
        for hit in hits:
            evidence.append(_chunk_evidence(hit))
        gaps = _section_gaps(family, heading, topic, kos, hits)
        status = _generation_status(family, kos, gaps)
        ko_labels = [item.label for item, _retrieved, _score in kos]
        objective = _objective(heading, title, ko_labels, gaps)
        regulation_ids = list(package.regulatory_profile.regulation_ids) if family == "references" else []
        built_sections.append(
            {
                "section_key": key,
                "heading": heading,
                "objective": objective,
                "knowledge_object_ids": [item.id for item, _r, _s in kos],
                "source_chunk_ids": [hit.chunk_id for hit in hits],
                "regulation_ids": regulation_ids,
                "evidence": evidence,
                "gaps": gaps,
                "generation_status": status,
            }
        )

    statuses = [section["generation_status"] for section in built_sections]
    gap_count = sum(len(section["gaps"]) for section in built_sections)
    return {
        "title": title,
        "topic": topic,
        "structure_source": structure_source,
        "structure_source_note": structure_note,
        "structure_source_document_id": structure_document_id,
        "generation_guidance": guidance,
        "unmapped_knowledge": unmapped,
        "sections": built_sections,
        "company_regulation_ids": list(package.regulatory_profile.regulation_ids),
        "summary": {
            "grounded": statuses.count("grounded"),
            "partial": statuses.count("partial"),
            "blocked": statuses.count("blocked"),
            "gap_count": gap_count,
            "verified_knowledge_mapped": len(mapped_ids),
            "fallback_structure": structure_source == "generic_fallback",
            "verified_pool_size": package.metadata.verified_pool_size,
        },
        "retrieval_notes": list(package.notes),
    }


def embed_texts(llm: Any, texts: list[str]) -> list[tuple[str, list[float]]]:
    if not texts:
        return []
    try:
        vectors = llm.embed(texts, task="query")
    except TypeError:
        vectors = llm.embed(texts)
    return list(zip(texts, vectors, strict=False))


def _resolve_structure(
    db: Session,
    company_id: uuid.UUID,
    trusted: list[KnowledgeObject],
    hits: list[RetrievedChunk],
) -> tuple[list[tuple[str, str, str]], str, str, uuid.UUID | None]:
    structure_kos = [item for item in trusted if item.type == STRUCTURE_TYPE]
    headings, document_id, note = _headings_from_structure_kos(structure_kos)
    if headings:
        return (
            _sections_from_headings(headings),
            "verified_document_structure",
            note or "Section outline taken from verified company document_structure knowledge.",
            document_id,
        )

    uploaded = _headings_from_uploaded_sop(db, company_id, hits)
    if uploaded is not None:
        headings, document_id, filename = uploaded
        return (
            _sections_from_headings(headings),
            "uploaded_sop_structure",
            (
                f"No verified document_structure knowledge. Outline taken from uploaded SOP "
                f"'{filename}'. Supporting chunks are evidence, not verified company facts."
            ),
            document_id,
        )

    sections = [(key, heading, family) for key, heading, family in GENERIC_SECTIONS]
    return (
        sections,
        "generic_fallback",
        "No verified company document_structure and no usable uploaded SOP outline. Generic fallback structure is used.",
        None,
    )


def _headings_from_structure_kos(
    items: list[KnowledgeObject],
) -> tuple[list[str], uuid.UUID | None, str]:
    preferred = sorted(items, key=lambda item: (-int(bool(item.source_document_id)), -item.version))
    for item in preferred:
        payload = item.payload if isinstance(item.payload, dict) else {}
        paths = payload.get("headingPaths") or payload.get("heading_paths")
        headings: list[str] = []
        if isinstance(paths, list):
            seen: set[str] = set()
            for path in paths:
                if not isinstance(path, list) or not path:
                    continue
                heading = str(path[0]).strip()
                key = heading.casefold()
                if heading and key not in seen:
                    seen.add(key)
                    headings.append(heading)
        if not headings:
            headings = _headings_from_label(item.label)
        if len(headings) >= 3:
            return headings, item.source_document_id, f"Verified document_structure: {item.label}"
    return [], None, ""


def _headings_from_label(label: str) -> list[str]:
    parts = [part.strip(" .") for part in re.split(r"[,;/|]|\band\b", label, flags=re.I)]
    known = []
    for part in parts:
        if not part:
            continue
        family = _family_of_text(part)
        if family:
            known.append(part.upper() if part.isupper() or len(part) < 40 else part)
    return known


def _headings_from_uploaded_sop(
    db: Session,
    company_id: uuid.UUID,
    hits: list[RetrievedChunk],
) -> tuple[list[str], uuid.UUID, str] | None:
    document_id = _preferred_document_id(db, company_id, hits)
    if document_id is None:
        return None
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.company_id == company_id)
    )
    if document is None:
        return None
    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.company_id == company_id,
            )
            .order_by(DocumentChunk.chunk_order)
        ).all()
    )
    headings: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not chunk.heading_path:
            continue
        heading = str(chunk.heading_path[0]).strip()
        key = heading.casefold()
        if heading and key not in seen:
            seen.add(key)
            headings.append(heading)
    if len(headings) < 3:
        return None
    return headings, document.id, document.filename


def _preferred_document_id(
    db: Session, company_id: uuid.UUID, hits: list[RetrievedChunk]
) -> uuid.UUID | None:
    counts: dict[uuid.UUID, int] = defaultdict(int)
    for hit in hits:
        counts[hit.document_id] += 1
    if counts:
        return max(counts, key=counts.get)
    sop = db.scalar(
        select(Document)
        .where(Document.company_id == company_id, Document.kind == DocumentKind.SOP)
        .order_by(Document.created_at.desc())
    )
    return sop.id if sop is not None else None


def _sections_from_headings(headings: list[str]) -> list[tuple[str, str, str]]:
    used: set[str] = set()
    sections: list[tuple[str, str, str]] = []
    for heading in headings:
        family = _family_of_text(heading) or "other"
        key = _slug(heading)
        if key in used:
            key = f"{key}_{len(used)}"
        used.add(key)
        sections.append((key, heading, family))
    return sections


def _slug(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", heading.casefold()).strip("_")
    return slug or "section"


def _family_of_text(text: str) -> str | None:
    lowered = text.casefold()
    for family, needles in FAMILY_PATTERNS:
        if any(needle in lowered for needle in needles):
            return family
    return None


def _assign_section(
    item: KnowledgeObject,
    retrieved: RetrievedKnowledge | None,
    sections: list[tuple[str, str, str]],
    topic: str,
    embed_pairs: list[tuple[str, list[float]]] | None,
) -> tuple[str | None, float]:
    families = TYPE_FAMILIES.get(item.type, ())
    candidates = [row for row in sections if row[2] in families] or list(sections)
    if not candidates:
        return None, 0.0
    location = ""
    if retrieved is not None:
        location = retrieved.citation.source_location
    haystack = f"{item.label} {item.source_location} {location}"
    heading_match = _section_for_heading(item.source_location or location, candidates)
    best_key = heading_match or candidates[0][0]
    best_score = 0.55 if heading_match else 0.35
    query = f"{item.type} {item.label} {topic}"
    for key, heading, _family in candidates:
        score = _text_similarity(query, heading, embed_pairs)
        lexical = _lexical_overlap(haystack, heading)
        score = max(score, lexical)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key, round(best_score, 4)


def _section_for_heading(
    heading: str, sections: list[tuple[str, str, str]]
) -> str | None:
    if not heading:
        return None
    first = heading.split(">")[0].strip().casefold()
    for key, section_heading, _family in sections:
        if first == section_heading.casefold() or first in section_heading.casefold():
            return key
        if section_heading.casefold() in first:
            return key
    family = _family_of_text(heading)
    if family:
        for key, _heading, section_family in sections:
            if section_family == family:
                return key
    return None


def _closest_section_key(
    text: str,
    sections: list[tuple[str, str, str]],
    embed_pairs: list[tuple[str, list[float]]] | None,
) -> str | None:
    if not sections:
        return None
    best_key = sections[0][0]
    best = 0.0
    for key, heading, _family in sections:
        score = max(_text_similarity(text, heading, embed_pairs), _lexical_overlap(text, heading))
        if score > best:
            best = score
            best_key = key
    return best_key if best >= 0.2 else sections[0][0]


def _text_similarity(
    left: str, right: str, embed_pairs: list[tuple[str, list[float]]] | None
) -> float:
    if not embed_pairs:
        return _lexical_overlap(left, right)
    vectors = {text: vector for text, vector in embed_pairs}
    a = vectors.get(left)
    b = vectors.get(right)
    if not a or not b:
        return _lexical_overlap(left, right)
    return cosine_similarity(a, b)


def _lexical_overlap(left: str, right: str) -> float:
    left_terms = {token for token in re.findall(r"[a-z0-9]{3,}", left.casefold())}
    right_terms = {token for token in re.findall(r"[a-z0-9]{3,}", right.casefold())}
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / len(right_terms)


def _knowledge_evidence(
    item: KnowledgeObject,
    retrieved: RetrievedKnowledge | None,
    names: dict[uuid.UUID | None, str],
    similarity: float | None = None,
) -> dict[str, Any]:
    snippet = None
    payload = item.payload if isinstance(item.payload, dict) else {}
    evidence = payload.get("evidence")
    if isinstance(evidence, list) and evidence and isinstance(evidence[0], dict):
        snippet = str(evidence[0].get("snippet") or "")[:SNIPPET_CHARS] or None
    citation = retrieved.citation if retrieved is not None else None
    return {
        "kind": "verified_knowledge",
        "id": item.id,
        "label": item.label,
        "type": item.type,
        "tier": str(item.tier),
        "status": str(item.status),
        "similarity": similarity if similarity is not None else (retrieved.similarity if retrieved else None),
        "source_document_id": item.source_document_id,
        "source_document_name": (citation.source_document_name if citation else names.get(item.source_document_id)),
        "source_chunk_id": item.source_chunk_id,
        "source_location": item.source_location,
        "snippet": snippet,
        "verified_by": item.verified_by,
        "verified_at": item.verified_at.isoformat() if item.verified_at else None,
    }


def _chunk_evidence(hit: RetrievedChunk) -> dict[str, Any]:
    return {
        "kind": "source_chunk",
        "id": hit.chunk_id,
        "label": hit.document_filename,
        "type": None,
        "tier": hit.tier,
        "status": "source_evidence",
        "similarity": round(hit.similarity, 4),
        "source_document_id": hit.document_id,
        "source_document_name": hit.document_filename,
        "source_chunk_id": hit.chunk_id,
        "source_location": hit.location,
        "snippet": hit.text[:SNIPPET_CHARS],
        "verified_by": None,
        "verified_at": None,
    }


def _section_gaps(
    family: str,
    heading: str,
    topic: str,
    kos: list[tuple[KnowledgeObject, RetrievedKnowledge | None, float]],
    hits: list[RetrievedChunk],
) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    required = family in REQUIRED_FAMILIES
    if not kos:
        gaps.append(
            {
                "field": f"verified_{family}_knowledge",
                "reason": (
                    f"No verified company Knowledge Object is mapped to '{heading}'. "
                    "Proposed, rejected and superseded objects are not trusted."
                ),
                "severity": "required" if required else "optional",
            }
        )
        if hits and required:
            gaps.append(
                {
                    "field": "unverified_source_evidence",
                    "reason": (
                        "Uploaded document chunks are available as supporting evidence only "
                        "and must not be treated as verified company facts."
                    ),
                    "severity": "required",
                }
            )
    haystack = " ".join(item.label for item, _r, _s in kos).casefold()
    if _is_training_topic(topic):
        if family in {"procedure", "training_users"} and not _mentions(haystack, ("frequen", "annual", "interval", "retrain")):
            gaps.append(
                {
                    "field": "training_or_retraining_frequency",
                    "reason": "No verified company rule found for training or retraining frequency.",
                    "severity": "required" if family == "procedure" else "optional",
                }
            )
        if family == "records" and not _mentions(haystack, ("retention", "archiv", "record", "form", "log")):
            gaps.append(
                {
                    "field": "training_record_retention_period",
                    "reason": "No verified company rule found for training-record retention.",
                    "severity": "required",
                }
            )
    return gaps


def _generation_status(
    family: str,
    kos: list,
    gaps: list[dict[str, str]],
) -> str:
    required_gaps = [gap for gap in gaps if gap["severity"] == "required"]
    if kos and not required_gaps:
        return "grounded"
    if kos and required_gaps:
        return "partial"
    if family in REQUIRED_FAMILIES:
        return "blocked"
    return "partial"


def _objective(heading: str, title: str, labels: list[str], gaps: list[dict[str, str]]) -> str:
    parts = [
        f"Cover '{heading}' for '{title}' using only mapped verified company knowledge and cited source chunks."
    ]
    if labels:
        parts.append("Verified knowledge mapped: " + "; ".join(labels[:8]) + ".")
    else:
        parts.append("No verified company facts are mapped; do not invent content for this section.")
    if gaps:
        parts.append("Known gaps: " + "; ".join(gap["reason"] for gap in gaps[:4]))
    return " ".join(parts)


def _is_training_topic(topic: str) -> bool:
    lowered = topic.casefold()
    return "train" in lowered or "retrain" in lowered or "gxp personnel" in lowered


def _mentions(haystack: str, needles: Iterable[str]) -> bool:
    return any(needle in haystack for needle in needles)
