from datetime import UTC, datetime

from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.models import KnowledgeObject
from app.modules.knowledge.service import KnowledgeService
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService
from app.modules.auth.models import UserCompanyAccess
from app.integrations.llm.base import Completion
from sqlalchemy import select
from app.shared.enums import DocumentStatus, KnowledgeStatus, KnowledgeTier


def test_list_returns_company_scoped_knowledge(client, db_session, auth_headers, company):
    document = Document(
        company_id=company["id"],
        filename="source.docx",
        source_format="docx",
        status=DocumentStatus.PROCESSED,
        page_count=1,
        byte_size=100,
        warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    item = KnowledgeObject(
        company_id=company["id"],
        type="terminology",
        tier=KnowledgeTier.COMPANY,
        status=KnowledgeStatus.PROPOSED,
        label="QA Manager",
        payload={"preferred": "QA Manager"},
        source_document_id=document.id,
        source_location="1. Responsibilities",
        extraction_method="test-fixture",
        extracted_at=datetime.now(UTC),
    )
    db_session.add(item)
    db_session.flush()

    response = client.get(
        f"/api/v1/companies/{company['id']}/knowledge-objects", headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["label"] == "QA Manager"
    assert body["items"][0]["status"] == "proposed"
    assert body["items"][0]["sourceDocumentId"] == str(document.id)


def test_knowledge_list_preserves_company_isolation(
    client, auth_headers, company, user_factory
):
    other = user_factory()
    response = client.get(
        f"/api/v1/companies/{company['id']}/knowledge-objects", headers=other
    )
    assert response.status_code == 404


def test_confirm_edit_and_reject_are_explicit_human_actions(
    client, db_session, auth_headers, company
):
    document = Document(company_id=company["id"], filename="review.docx", source_format="docx",
                        status=DocumentStatus.PROCESSED, page_count=1, byte_size=20, warnings=[])
    db_session.add(document)
    db_session.flush()
    items = []
    for label in ("Confirm me", "Reject me"):
        item = KnowledgeObject(company_id=company["id"], type="business_rule",
            tier=KnowledgeTier.COMPANY, status=KnowledgeStatus.PROPOSED, label=label,
            payload={}, source_document_id=document.id, source_location="Rules",
            extraction_method="test-fixture", extracted_at=datetime.now(UTC))
        db_session.add(item)
        items.append(item)
    db_session.flush()

    edited = client.patch(f"/api/v1/companies/{company['id']}/knowledge-objects/{items[0].id}",
                          headers=auth_headers, json={"label": "Edited rule"})
    assert edited.status_code == 200
    assert edited.json()["label"] == "Edited rule"
    confirmed = client.post(f"/api/v1/companies/{company['id']}/knowledge-objects/{items[0].id}/confirm",
                            headers=auth_headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "verified"
    assert confirmed.json()["verifiedBy"] is not None
    rejected = client.post(f"/api/v1/companies/{company['id']}/knowledge-objects/{items[1].id}/reject",
                           headers=auth_headers)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


class _FakeLocalProvider:
    name = "fake-local"
    chat_model = "test-model"
    embedding_model = "test-embedding"
    embedding_dimensions = 768

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        import json
        source_chunk_id = json.loads(messages[-1].content)[0]["id"]
        return Completion(
            text=json.dumps([
                {"type": "regulation", "label": "EU GMP", "sourceChunkId": source_chunk_id, "payload": {}},
                {"type": "role", "label": "QA approves", "sourceChunkId": source_chunk_id, "payload": {}},
                {"type": "workflow", "label": "Draft then approve", "sourceChunkId": source_chunk_id, "payload": {}},
                {"type": "business_rule", "label": "Approval required", "sourceChunkId": source_chunk_id, "payload": {}},
            ]),
            model=self.chat_model, provider=self.name,
        )


def test_extraction_uses_stored_chunks_and_keeps_provenance(db_session, company, auth_headers):
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company["id"]))
    document = Document(company_id=company["id"], filename="source.docx", source_format="docx",
                        status=DocumentStatus.PROCESSED, page_count=1, byte_size=50, warnings=[])
    db_session.add(document)
    db_session.flush()
    chunk = DocumentChunk(document_id=document.id, company_id=company["id"],
                          tier=KnowledgeTier.COMPANY, chunk_order=0,
                          heading_path=["3. Procedure"], text="Follow EU GMP and Annex 11.")
    db_session.add(chunk)
    db_session.flush()
    service = KnowledgeService(db_session, CompanyService(db_session, CompanyRepository(db_session)))

    created, skipped = service.extract_from_chunks(access.user_id, document.company_id, _FakeLocalProvider())
    objects = list(db_session.scalars(select(KnowledgeObject).where(
        KnowledgeObject.company_id == document.company_id)).all())

    assert created == 7
    assert skipped == 0
    assert {item.type for item in objects} == {
        "terminology", "writing_style", "document_structure", "regulation", "role", "workflow", "business_rule"
    }
    assert all(item.status == KnowledgeStatus.PROPOSED for item in objects)
    assert all(item.source_document_id == document.id and item.source_chunk_id == chunk.id for item in objects)
    terminology = [item.label for item in objects if item.type == "terminology"]
    assert terminology == ["Good Manufacturing Practice (GMP)"]
    assert not {"NAME", "COMPANY", "II", "IV", "VI", "EU", "GMP-", "WI-LL-", "FRM-LL-"} & set(terminology)
    structure = next(item for item in objects if item.type == "document_structure")
    assert structure.payload["headingPaths"] == [["3. Procedure"]]
    assert all(item.source_location != "(no section)" for item in objects)

    created_again, skipped_again = service.extract_from_chunks(
        access.user_id, document.company_id, _FakeLocalProvider()
    )
    objects_again = list(db_session.scalars(select(KnowledgeObject).where(
        KnowledgeObject.company_id == document.company_id)).all())
    assert created_again == 0
    assert skipped_again == 1
    assert len(objects_again) == len(objects)
