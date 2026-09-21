"""Parse and filter LLM CKM extraction payloads."""

from __future__ import annotations

import json
import re
from typing import Any

from app.modules.documents.models import DocumentChunk

CKM_EXTRACT_PROMPT_VERSION = "ckm_extract_v4"

# Types the LLM may propose. Deterministic extraction owns terminology,
# document_structure and writing_style — do not accept those from the model.
SEMANTIC_TYPES = frozenset(
    {
        "regulation",
        "role",
        "responsibility",
        "workflow",
        "process",
        "business_rule",
        "form_or_record",
        "relationship",
        "best_practice",
    }
)

DETERMINISTIC_TYPES = frozenset({"terminology", "document_structure", "writing_style"})

CKM_EXTRACT_SYSTEM = (
    "Extract only knowledge explicitly supported by the supplied SOP chunks. "
    "Respond with a JSON array (not an object) of at most 30 compact objects. "
    "Each element must be: "
    '{"type":"<one of regulation,role,responsibility,workflow,process,'
    'business_rule,form_or_record,relationship,best_practice>",'
    '"label":"<concise grounded label>",'
    '"sourceChunkId":"<id from an input chunk>",'
    '"payload":{"evidence":"<verbatim substring of that chunk, max 180 characters>"}}. '
    "sourceChunkId must match an input chunk id. evidence must appear in that chunk. "
    "Prefer distinct roles, responsibilities, workflows, processes, business rules, "
    "forms or records, relationships, and explicitly stated best practices. "
    "Do not emit terminology, document_structure, or writing_style. "
    "Do not invent roles, processes, rules, forms or relationships that are not in the text. "
    "Omit unsupported items. Empty array is valid. Stop after 30 items."
)

# Gemini JSON mode often wraps the array in a named object.
_WRAPPER_KEYS = (
    "items",
    "objects",
    "knowledge",
    "knowledgeObjects",
    "results",
    "data",
    "candidates",
    "extractions",
)


def parse_knowledge_array(raw: str) -> tuple[list[Any], dict[str, Any]]:
    """Return (values, diagnostics). values is always a list (possibly empty)."""
    diagnostics: dict[str, Any] = {
        "response_chars": len(raw or ""),
        "json_root_type": None,
        "parse_ok": False,
        "raw_item_count": 0,
        "parse_error": None,
        "unwrapped": False,
        "repaired": False,
    }
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    if not cleaned:
        diagnostics["parse_error"] = "empty"
        return [], diagnostics
    try:
        decoded = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError) as exc:
        recovered = recover_truncated_json(cleaned)
        if recovered is None:
            diagnostics["parse_error"] = type(exc).__name__
            return [], diagnostics
        diagnostics["repaired"] = True
        diagnostics["parse_error"] = type(exc).__name__
        decoded = recovered
    diagnostics["json_root_type"] = type(decoded).__name__
    diagnostics["parse_ok"] = True
    values, unwrapped = _coerce_list(decoded)
    diagnostics["unwrapped"] = unwrapped
    diagnostics["raw_item_count"] = len(values)
    return values, diagnostics


def recover_truncated_json(raw: str) -> Any | None:
    """Keep complete objects from a truncated JSON array; never invent the tail."""
    text = (raw or "").lstrip()
    if not text.startswith("["):
        return None
    decoder = json.JSONDecoder()
    items: list[Any] = []
    index = 1
    length = len(text)
    while index < length:
        while index < length and text[index] in " \t\r\n,":
            index += 1
        if index >= length or text[index] == "]":
            break
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break
        items.append(value)
        index = end
    return items or None


def _coerce_list(decoded: Any) -> tuple[list[Any], bool]:
    if isinstance(decoded, list):
        return decoded, False
    if isinstance(decoded, dict):
        for key in _WRAPPER_KEYS:
            inner = decoded.get(key)
            if isinstance(inner, list):
                return inner, True
        if "type" in decoded and "label" in decoded:
            return [decoded], True
        lists = [value for value in decoded.values() if isinstance(value, list)]
        if len(lists) == 1:
            return lists[0], True
    return [], False


def semantic_candidates(
    raw: str, chunks: list[DocumentChunk], analysis_hash: str = ""
) -> tuple[list[tuple[str, str, dict, str, DocumentChunk]], dict[str, Any]]:
    values, diagnostics = parse_knowledge_array(raw)
    by_id = {str(chunk.id): chunk for chunk in chunks}
    result: list[tuple[str, str, dict, str, DocumentChunk]] = []
    dropped = {
        "not_object": 0,
        "type_not_allowed": 0,
        "missing_label": 0,
        "unknown_chunk": 0,
        "no_heading": 0,
        "evidence_mismatch": 0,
    }
    for value in values:
        if not isinstance(value, dict):
            dropped["not_object"] += 1
            continue
        kind = value.get("type")
        if kind in DETERMINISTIC_TYPES or kind not in SEMANTIC_TYPES:
            dropped["type_not_allowed"] += 1
            continue
        label = str(value.get("label", "")).strip()[:500]
        if not label:
            dropped["missing_label"] += 1
            continue
        payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
        source = by_id.get(str(value.get("sourceChunkId")))
        if source is None:
            dropped["unknown_chunk"] += 1
            continue
        if not source.heading_path:
            dropped["no_heading"] += 1
            continue
        evidence = str(payload.pop("evidence", "")).strip()
        if evidence and evidence.casefold() not in source.text.casefold():
            dropped["evidence_mismatch"] += 1
            continue
        result.append((str(kind), label, payload, "local-llm-document", source))
    diagnostics["kept"] = len(result)
    diagnostics["dropped"] = dropped
    return result, diagnostics
