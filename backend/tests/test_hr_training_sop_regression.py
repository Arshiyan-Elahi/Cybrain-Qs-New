"""
Property-based regression for SOP-HR-001 when the source DOCX is available.

Does not hardcode production chunk/object counts. Skips if the file is absent.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.auth.models import UserCompanyAccess
from app.modules.documents.ingestion import IngestionService
from app.modules.documents.models import DocumentChunk
from app.modules.knowledge.service import KnowledgeService
from app.processing.chunker import chunk_document
from app.processing.extractor import extract
from app.shared.enums import DocumentStatus

HR_SOP = Path(
    r"C:\Users\DilshadAli(ITOps)\Downloads\SOPs\SOPs\Client 1"
    r"\SOP-HR-001 V6 Qualification Training and Retraining of GxP personnel.docx"
)


@pytest.fixture(scope="module")
def hr_bytes():
    if not HR_SOP.is_file():
        pytest.skip(f"HR SOP fixture not found: {HR_SOP}")
    return HR_SOP.read_bytes(), HR_SOP.name


def test_hr_sop_parser_normalizes_hierarchy_and_excludes_approval(hr_bytes):
    content, filename = hr_bytes
    extracted = extract(content, filename)
    chunks = chunk_document(extracted)
    semantic = [c for c in chunks if c.is_semantic]
    non_semantic = [c for c in chunks if not c.is_semantic]

    assert chunks
    assert all(c.heading_path for c in semantic)
    assert non_semantic
    assert all(
        any(b["type"] == "approval_signature" for b in c.blocks) for c in non_semantic
    )
    assert not any(
        any(b["type"] == "approval_signature" for b in c.blocks) for c in semantic
    )
    assert any(len(c.heading_path) >= 2 for c in semantic)
    assert any(any(b["type"] == "table" for b in c.blocks) for c in semantic)
    assert any(b.kind == "list" for b in extracted.blocks)
    text = "\n".join(c.text for c in chunks)
    for needle in ("QA", "OJT", "retrain", "training record", "trainer", "personnel"):
        assert needle.lower() in text.lower()


def test_hr_sop_no_semantic_source_without_section(hr_bytes):
    content, filename = hr_bytes
    chunks = chunk_document(extract(content, filename))
    for chunk in chunks:
        if chunk.is_semantic:
            assert "(no section)" not in chunk.location


def test_hr_sop_ingest_persists_semantic_provenance(db_session, company, hr_bytes):
    content, filename = hr_bytes
    access = db_session.scalar(
        select(UserCompanyAccess).where(UserCompanyAccess.company_id == company["id"])
    )
    document = IngestionService(db_session, llm=None).ingest(
        company_id=company["id"],
        filename=filename,
        content=content,
        uploaded_by=access.user_id,
        embed=False,
    )
    assert document.status == DocumentStatus.PROCESSED
    chunks = list(db_session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == document.id)
    ).all())
    semantic = [c for c in chunks if c.is_semantic]
    assert semantic
    assert not any(
        any(b.get("type") == "approval_signature" for b in (c.extra.get("blocks") or []))
        for c in semantic
        if c.heading_path
    )

    det = KnowledgeService._deterministic_candidates(chunks, filename, "test")
    assert all(src is None or "(no section)" not in src.location for *_rest, src in det)
    document_wide = [row for row in det if row[0] in ("document_structure", "writing_style")]
    assert document_wide
    assert all(src is None for *_rest, src in document_wide)
    terms = {label: src for kind, label, _payload, _method, src in det if kind == "terminology"}
    labels = set(terms)
    text = "\n".join(c.text for c in chunks)
    if "QA" in text or "Quality Assurance" in text:
        assert "Quality Assurance (QA)" in labels
        qa_src = terms["Quality Assurance (QA)"]
        assert qa_src is not None
        assert "REFERENCE" not in " ".join(qa_src.heading_path).upper()
        assert "SOP-QA-003" not in qa_src.text or "Quality Assurance" in qa_src.text
    if "OJT" in text or "On-the-Job" in text:
        assert "On-the-Job Training (OJT)" in labels
        ojt_src = terms["On-the-Job Training (OJT)"]
        assert ojt_src is not None
        heading = " / ".join(ojt_src.heading_path).lower()
        assert "reference" not in heading
