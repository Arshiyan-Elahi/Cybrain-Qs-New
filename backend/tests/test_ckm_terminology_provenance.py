"""Regression: deterministic CKM terminology provenance (SOP-HR-001 shape)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.integrations.llm.base import Completion
from app.modules.auth.models import UserCompanyAccess
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.models import KnowledgeObject
from app.modules.knowledge.service import DOCUMENT_SCOPE_LOCATION, KnowledgeService
from app.modules.knowledge.terminology import (
    TERM_PATTERNS,
    mask_document_ids,
    occurrence_count,
    select_terminology_chunk,
)
from app.shared.enums import DocumentStatus, KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier


def _chunk(order: int, path: list[str], text: str, *, semantic: bool = True) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        chunk_order=order,
        heading_path=path,
        text=text,
        extra={"isSemantic": semantic},
    )


def _hr_shaped_chunks() -> list[DocumentChunk]:
    return [
        _chunk(0, [], "SOP-HR-001 | Qualification, Training and Retraining"),
        _chunk(1, ["PURPOSE"], "This SOP describes training and qualification of personnel."),
        _chunk(
            2,
            ["REFERENCES"],
            "SOP-QA-003 SOP-QA-005 SOP-GCP-010\n"
            "Template OJT training\n"
            "The Rules Governing Medicinal Products in the European Union, Vol. 4 GMP\n"
            "ICH Guideline for Good Clinical Practice E6(R2)",
        ),
        _chunk(3, ["RESPONSIBILITIES"], "It is the responsibility of the QA to keep records of all training."),
        _chunk(
            4,
            ["DEFINITION AND ABBREVIATIONS", "Abbreviations"],
            "Annual GMP or GCP training provided by QA.\n"
            "GCP\tGood Clinical Practices\n"
            "GMP\tGood Manufacturing Practices\n"
            "OJT\tOn the Job Training\n"
            "QA\tQuality Assurance\n"
            "SOP\tStandard Operating Procedure",
        ),
        _chunk(
            5,
            ["PROCEDURE", "On-the-Job Training"],
            "After finalisation both trainee and trainer sign the OJT-form.",
        ),
    ]


def test_mask_document_ids_strips_structured_codes():
    masked = mask_document_ids("See SOP-QA-003, SOP-GCP-010 and SOP-HR-001 then the QA team.")
    assert "SOP-QA-003" not in masked
    assert "SOP-GCP-010" not in masked
    assert "SOP-HR-001" not in masked
    assert "QA team" in masked


def test_abbreviations_not_counted_inside_document_ids():
    qa = TERM_PATTERNS["Quality Assurance (QA)"]
    gcp = TERM_PATTERNS["Good Clinical Practice (GCP)"]
    sop = TERM_PATTERNS["Standard Operating Procedure (SOP)"]
    ids_only = "SOP-QA-003 SOP-GCP-010 SOP-HR-001"
    assert occurrence_count(ids_only, qa) == 0
    assert occurrence_count(ids_only, gcp) == 0
    assert occurrence_count(ids_only, sop) == 0
    standalone = "This SOP describes QA and GCP. SOP-QA-003 is a related document."
    assert occurrence_count(standalone, sop) == 1
    assert occurrence_count(standalone, qa) == 1
    assert occurrence_count(standalone, gcp) == 1


def test_hr_shaped_terminology_prefers_abbreviations_not_references():
    chunks = _hr_shaped_chunks()
    rows = KnowledgeService._deterministic_candidates(chunks, "SOP-HR-001.docx", "hash")
    terms = {label: (payload, src) for kind, label, payload, _m, src in rows if kind == "terminology"}

    qa_payload, qa_src = terms["Quality Assurance (QA)"]
    assert qa_src is not None
    assert qa_src.heading_path[-1] == "Abbreviations"
    assert "SOP-QA-003" not in qa_src.text
    assert "Quality Assurance" in qa_src.text
    assert "count" not in qa_payload
    assert qa_payload["occurrenceCount"] >= 1

    gcp_payload, gcp_src = terms["Good Clinical Practice (GCP)"]
    assert gcp_src is not None
    assert gcp_src.heading_path[-1] == "Abbreviations"
    assert "SOP-GCP-010" not in gcp_src.text
    assert "Good Clinical Practices" in gcp_src.text
    assert gcp_payload["occurrenceCount"] >= 1

    sop_src = terms["Standard Operating Procedure (SOP)"][1]
    assert sop_src is not None
    assert sop_src.heading_path[-1] == "Abbreviations"
    assert "Standard Operating Procedure" in sop_src.text

    gmp_src = terms["Good Manufacturing Practice (GMP)"][1]
    assert gmp_src is not None
    assert gmp_src.heading_path[-1] == "Abbreviations"

    ojt_src = terms["On-the-Job Training (OJT)"][1]
    assert ojt_src is not None
    heading = " / ".join(ojt_src.heading_path)
    assert "Abbreviations" in heading or "On-the-Job Training" in heading
    assert "REFERENCES" not in heading


def test_ojt_falls_back_to_procedure_when_no_definition_section():
    chunks = [
        _chunk(0, ["REFERENCES"], "Template OJT training SOP-QA-003"),
        _chunk(1, ["PROCEDURE", "On-the-Job Training"], "Sign the OJT form after on-the-job training."),
    ]
    source = select_terminology_chunk(chunks, TERM_PATTERNS["On-the-Job Training (OJT)"])
    assert source is not None
    assert source.heading_path == ["PROCEDURE", "On-the-Job Training"]


def test_document_wide_candidates_have_no_purpose_chunk():
    chunks = _hr_shaped_chunks()
    rows = KnowledgeService._deterministic_candidates(chunks, "SOP-HR-001.docx", "hash")
    wide = [row for row in rows if row[0] in ("document_structure", "writing_style")]
    assert len(wide) == 2
    for kind, _label, payload, method, src in wide:
        assert src is None
        assert payload["scope"] == "document"
        assert method == "deterministic"
        assert kind in ("document_structure", "writing_style")


class _EmptyLlm:
    name = "fake-empty"
    chat_model = "test-model"
    embedding_model = "test-embedding"
    embedding_dimensions = 768

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        return Completion(text="[]", model=self.chat_model, provider=self.name)


def test_extract_persists_hr_provenance_as_proposed_uploaded_document(
    db_session, company
):
    access = db_session.scalar(
        select(UserCompanyAccess).where(UserCompanyAccess.company_id == company["id"])
    )
    document = Document(
        company_id=company["id"],
        filename="SOP-HR-001.docx",
        source_format="docx",
        status=DocumentStatus.PROCESSED,
        page_count=5,
        byte_size=100,
        warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    for index, seed in enumerate(_hr_shaped_chunks()):
        db_session.add(
            DocumentChunk(
                document_id=document.id,
                company_id=company["id"],
                tier=KnowledgeTier.COMPANY,
                chunk_order=index,
                heading_path=list(seed.heading_path),
                text=seed.text,
                extra=dict(seed.extra),
            )
        )
    db_session.flush()

    service = KnowledgeService(db_session, CompanyService(db_session, CompanyRepository(db_session)))
    created, skipped = service.extract_from_chunks(access.user_id, company["id"], _EmptyLlm())
    assert skipped == 0
    assert created >= 7

    items = list(
        db_session.scalars(
            select(KnowledgeObject).where(KnowledgeObject.company_id == company["id"])
        ).all()
    )
    assert all(item.status == KnowledgeStatus.PROPOSED for item in items)
    assert all(item.tier == KnowledgeTier.COMPANY for item in items)
    document_items = [item for item in items if item.source_document_id == document.id]
    assert {item.source_kind for item in document_items} == {KnowledgeSourceKind.UPLOADED_DOCUMENT}

    qa = next(item for item in document_items if item.label == "Quality Assurance (QA)")
    assert qa.source_chunk_id is not None
    assert "Abbreviations" in qa.source_location
    assert "REFERENCES" not in qa.source_location
    snippet = qa.payload["evidence"][0]["snippet"]
    assert "SOP-QA-003" not in snippet
    assert "Quality Assurance" in snippet
    assert "count" not in qa.payload

    gcp = next(item for item in document_items if item.label == "Good Clinical Practice (GCP)")
    assert "Abbreviations" in gcp.source_location
    assert "SOP-GCP-010" not in gcp.payload["evidence"][0]["snippet"]

    ojt = next(item for item in document_items if item.label == "On-the-Job Training (OJT)")
    assert "REFERENCES" not in ojt.source_location

    structure = next(item for item in document_items if item.type == "document_structure")
    writing = next(item for item in document_items if item.type == "writing_style")
    for item in (structure, writing):
        assert item.source_chunk_id is None
        assert item.source_location == DOCUMENT_SCOPE_LOCATION
        assert item.payload.get("scope") == "document"
        assert item.source_document_id == document.id
        assert item.payload["evidence"][0].get("scope") == "document"
        assert "PURPOSE" not in item.source_location
