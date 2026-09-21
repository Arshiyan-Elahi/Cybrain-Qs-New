"""Parse, unwrap and filter LLM CKM extraction payloads."""

from __future__ import annotations

import uuid

from app.modules.knowledge.semantic_extract import (
    parse_knowledge_array,
    semantic_candidates,
)


class _Chunk:
    def __init__(self, text: str, heading_path: list[str] | None = None):
        self.id = uuid.uuid4()
        self.heading_path = heading_path if heading_path is not None else ["4. Responsibilities"]
        self.text = text


def test_parse_valid_json_array():
    values, diag = parse_knowledge_array(
        '[{"type":"role","label":"Trainer","sourceChunkId":"abc"}]'
    )
    assert diag["parse_ok"] is True
    assert diag["json_root_type"] == "list"
    assert diag["unwrapped"] is False
    assert len(values) == 1
    assert values[0]["type"] == "role"


def test_parse_unwraps_gemini_object_wrapper():
    raw = '{"knowledgeObjects":[{"type":"workflow","label":"Retrain","sourceChunkId":"x"}]}'
    values, diag = parse_knowledge_array(raw)
    assert diag["parse_ok"] is True
    assert diag["json_root_type"] == "dict"
    assert diag["unwrapped"] is True
    assert values[0]["label"] == "Retrain"


def test_parse_empty_and_malformed():
    empty, empty_diag = parse_knowledge_array("")
    assert empty == []
    assert empty_diag["parse_error"] == "empty"

    blank_array, blank_diag = parse_knowledge_array("[]")
    assert blank_array == []
    assert blank_diag["parse_ok"] is True
    assert blank_diag["raw_item_count"] == 0

    bad, bad_diag = parse_knowledge_array('[{"type":"role"')
    assert bad == []
    assert bad_diag["parse_error"] == "JSONDecodeError"
    assert bad_diag["repaired"] is False


def test_parse_recovers_complete_objects_from_truncated_array():
    raw = (
        '[\n'
        '  {"type":"role","label":"Trainer","sourceChunkId":"abc","payload":{"evidence":"Trainer"}},\n'
        '  {"type":"workflow","label":"Retrain after deviation","sourceChunkId":"abc","payload":{"evidence":"Retrain af'
    )
    values, diag = parse_knowledge_array(raw)
    assert diag["repaired"] is True
    assert diag["parse_ok"] is True
    assert diag["raw_item_count"] == 1
    assert values[0]["type"] == "role"
    assert values[0]["label"] == "Trainer"


def test_keeps_grounded_semantic_types_with_chunk_evidence():
    chunk = _Chunk("The Training Coordinator assigns trainers and maintains records.")
    raw = (
        '[{"type":"role","label":"Training Coordinator",'
        f'"sourceChunkId":"{chunk.id}",'
        '"payload":{"evidence":"Training Coordinator assigns trainers"}}]'
    )
    kept, diag = semantic_candidates(raw, [chunk])  # type: ignore[arg-type]
    assert diag["kept"] == 1
    kind, label, payload, method, source = kept[0]
    assert kind == "role"
    assert label == "Training Coordinator"
    assert "evidence" not in payload
    assert method == "local-llm-document"
    assert source is chunk


def test_filters_deterministic_types_unknown_chunks_and_bad_evidence():
    chunk = _Chunk("Employees shall complete induction training before GxP work.")
    raw = (
        "["
        f'{{"type":"terminology","label":"GxP","sourceChunkId":"{chunk.id}","payload":{{}}}},'
        f'{{"type":"document_structure","label":"SOP structure","sourceChunkId":"{chunk.id}","payload":{{}}}},'
        f'{{"type":"writing_style","label":"style","sourceChunkId":"{chunk.id}","payload":{{}}}},'
        f'{{"type":"role","label":"Ghost role","sourceChunkId":"{uuid.uuid4()}","payload":{{}}}},'
        f'{{"type":"business_rule","label":"Invented rule","sourceChunkId":"{chunk.id}",'
        '"payload":{"evidence":"this phrase is not in the chunk"}},'
        f'{{"type":"workflow","label":"Induction before GxP work","sourceChunkId":"{chunk.id}",'
        '"payload":{"evidence":"complete induction training before GxP"}}'
        "]"
    )
    kept, diag = semantic_candidates(raw, [chunk])  # type: ignore[arg-type]
    assert diag["dropped"]["type_not_allowed"] == 3
    assert diag["dropped"]["unknown_chunk"] == 1
    assert diag["dropped"]["evidence_mismatch"] == 1
    assert diag["kept"] == 1
    assert kept[0][0] == "workflow"
    assert kept[0][1] == "Induction before GxP work"


def test_drops_headingless_chunks_and_unsupported_types():
    headed = _Chunk("QA reviews training records.")
    bare = _Chunk("Cover page", heading_path=[])
    raw = (
        "["
        f'{{"type":"best_practice","label":"QA review of records","sourceChunkId":"{headed.id}",'
        '"payload":{"evidence":"QA reviews training records"}},'
        f'{{"type":"role","label":"Cover clerk","sourceChunkId":"{bare.id}","payload":{{}}}},'
        f'{{"type":"unicorn","label":"Hallucination","sourceChunkId":"{headed.id}","payload":{{}}}}'
        "]"
    )
    kept, diag = semantic_candidates(raw, [headed, bare])  # type: ignore[arg-type]
    assert {row[0] for row in kept} == {"best_practice"}
    assert diag["dropped"]["no_heading"] == 1
    assert diag["dropped"]["type_not_allowed"] == 1
    assert diag["kept"] == 1
