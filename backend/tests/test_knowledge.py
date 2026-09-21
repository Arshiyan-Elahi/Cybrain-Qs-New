from datetime import UTC, datetime

from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.models import KnowledgeObject
from app.modules.knowledge.service import KnowledgeService
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService
from app.modules.auth.models import UserCompanyAccess
from app.integrations.llm.base import Completion
from sqlalchemy import select
from app.shared.enums import DocumentStatus, KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier


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
        source_kind=KnowledgeSourceKind.UPLOADED_DOCUMENT,
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
            payload={}, source_kind=KnowledgeSourceKind.UPLOADED_DOCUMENT,
            source_document_id=document.id, source_location="Rules",
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
    assert all(item.source_document_id == document.id for item in objects)
    document_wide = [item for item in objects if item.type in ("document_structure", "writing_style")]
    grounded = [item for item in objects if item.type not in ("document_structure", "writing_style")]
    assert all(item.source_chunk_id is None and item.source_location == "document" for item in document_wide)
    assert all(item.payload.get("scope") == "document" for item in document_wide)
    assert all(item.source_chunk_id == chunk.id for item in grounded)
    assert {item.source_kind for item in objects if item.extraction_method == "deterministic"} == {
        KnowledgeSourceKind.UPLOADED_DOCUMENT
    }
    assert {item.source_kind for item in objects if item.extraction_method.startswith("local-llm")} == {
        KnowledgeSourceKind.AI_EXTRACTED
    }
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


class _GeminiWrappedProvider:
    """Mimic Gemini JSON-mode wrapping plus hallucinated deterministic types."""

    name = "routing"
    chat_model = "qwen/qwen2.5-vl-7b"
    embedding_model = "test-embedding"
    embedding_dimensions = 768

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        import json

        source_chunk_id = json.loads(messages[-1].content)[0]["id"]
        return Completion(
            text=json.dumps(
                {
                    "knowledgeObjects": [
                        {
                            "type": "role",
                            "label": "QA approver",
                            "sourceChunkId": source_chunk_id,
                            "payload": {"evidence": "Follow EU GMP and Annex 11."},
                        },
                        {
                            "type": "terminology",
                            "label": "Annex 11",
                            "sourceChunkId": source_chunk_id,
                            "payload": {},
                        },
                        {
                            "type": "unicorn",
                            "label": "Invented object",
                            "sourceChunkId": source_chunk_id,
                            "payload": {"evidence": "not in the chunk at all"},
                        },
                    ]
                }
            ),
            model="gemini-2.5-flash",
            provider="gemini",
        )


class _MalformedGeminiProvider:
    name = "routing"
    chat_model = "qwen/qwen2.5-vl-7b"
    embedding_model = "test-embedding"
    embedding_dimensions = 768

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        return Completion(
            text='{"type":"role","label":"truncated"',
            model="gemini-2.5-flash",
            provider="gemini",
        )


def _seed_extract_document(db_session, company):
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company["id"]))
    document = Document(
        company_id=company["id"],
        filename="source.docx",
        source_format="docx",
        status=DocumentStatus.PROCESSED,
        page_count=1,
        byte_size=50,
        warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        company_id=company["id"],
        tier=KnowledgeTier.COMPANY,
        chunk_order=0,
        heading_path=["3. Procedure"],
        text="Follow EU GMP and Annex 11.",
    )
    db_session.add(chunk)
    db_session.flush()
    service = KnowledgeService(db_session, CompanyService(db_session, CompanyRepository(db_session)))
    return access, document, chunk, service


def test_extraction_unwraps_gemini_json_and_logs_actual_provider(db_session, company, caplog):
    import logging

    access, document, chunk, service = _seed_extract_document(db_session, company)
    caplog.set_level(logging.INFO, logger="app.knowledge")
    created, skipped = service.extract_from_chunks(
        access.user_id, document.company_id, _GeminiWrappedProvider()
    )
    objects = list(
        db_session.scalars(
            select(KnowledgeObject).where(KnowledgeObject.company_id == document.company_id)
        ).all()
    )
    by_type = {item.type: item for item in objects}
    assert skipped == 0
    assert created == 4  # structure, style, terminology, role
    assert "role" in by_type
    assert by_type["role"].label == "QA approver"
    assert by_type["role"].status == KnowledgeStatus.PROPOSED
    assert by_type["role"].source_kind == KnowledgeSourceKind.AI_EXTRACTED
    assert by_type["role"].source_chunk_id == chunk.id
    assert by_type["role"].model_provider == "gemini"
    assert by_type["role"].model_name == "gemini-2.5-flash"
    assert "unicorn" not in by_type
    assert not any(item.label == "Annex 11" for item in objects)
    assert not any(item.label == "Invented object" for item in objects)
    completed = [r for r in caplog.records if getattr(r, "event", None) == "ckm_extraction_completed"]
    assert completed
    extras = completed[-1].extra_fields
    assert extras["provider"] == "gemini"
    assert extras["model"] == "gemini-2.5-flash"
    parsed = [r for r in caplog.records if getattr(r, "event", None) == "ckm_llm_parse"]
    assert parsed
    assert parsed[-1].extra_fields["unwrapped"] is True
    assert parsed[-1].extra_fields["kept"] == 1


def test_malformed_gemini_response_keeps_only_deterministic(db_session, company):
    access, document, _chunk, service = _seed_extract_document(db_session, company)
    created, skipped = service.extract_from_chunks(
        access.user_id, document.company_id, _MalformedGeminiProvider()
    )
    objects = list(
        db_session.scalars(
            select(KnowledgeObject).where(KnowledgeObject.company_id == document.company_id)
        ).all()
    )
    assert skipped == 0
    assert created == 3
    assert {item.type for item in objects} == {
        "terminology",
        "writing_style",
        "document_structure",
    }
    assert all(item.extraction_method == "deterministic" for item in objects)
    assert all(item.status == KnowledgeStatus.PROPOSED for item in objects)
    assert all(item.model_provider is None for item in objects)


def test_onboarding_creates_proposed_knowledge_with_provenance(client, auth_headers, db_session):
    import uuid
    from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory
    from app.shared.enums import KnowledgeSourceKind, KnowledgeStatus
    from sqlalchemy import select

    response = client.post(
        "/api/v1/companies",
        headers=auth_headers,
        json={
            "name": "CKM Onboard Co",
            "industryKey": "pharma",
            "locationKey": "de",
            "primaryLanguageKey": "en",
            "regulationIds": [],
            "creationRequestId": str(uuid.uuid4()),
            "onboarding": {
                "startOptionId": "nothing",
                "documentPathId": "continue-without",
                "terminologyText": "batch record\nCAPA",
                "rolesText": "QA Manager",
                "processesText": "Deviation handling",
                "businessRulesText": "No silent overwrites",
                "formsText": "Change control form",
                "relationshipsText": "SOP links to forms",
                "bestPracticesText": "Cite sources",
                "structurePreferenceId": "standard",
                "documentStructureNotes": "Keep sections short",
                "toneId": "neutral",
                "formalityId": "formal",
                "personId": "third",
                "writingNotes": "Prefer clear verbs",
                "aiAssistLevelId": "balanced",
                "requireHumanVerification": True,
                "qualityNotes": "Human gate required",
                "preferExistingTerms": True,
                "departmentsText": "QA",
                "workflowNotes": "Two-step review",
                "templatePreferenceId": "gmp-default",
                "layoutNotes": "Numbered headings",
                "intendedDocumentNames": [],
                "intendedTemplateNames": [],
            },
        },
    )
    assert response.status_code == 201
    company_id = response.json()["id"]
    objects = list(db_session.scalars(select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)).all())
    assert len(objects) >= 8
    assert all(item.status == KnowledgeStatus.PROPOSED for item in objects)
    assert all(item.source_kind == KnowledgeSourceKind.ONBOARDING for item in objects)
    assert all(item.source_document_id is None for item in objects)
    assert all(item.extraction_method == "onboarding-profile" for item in objects)
    labels = {item.label for item in objects}
    assert "batch record" in labels
    assert "QA Manager" in labels
    history = list(db_session.scalars(select(KnowledgeObjectHistory).where(
        KnowledgeObjectHistory.company_id == company_id)).all())
    assert history
    assert all(row.action == "proposed_created" for row in history)

    again = client.post(f"/api/v1/companies/{company_id}/knowledge-objects/from-onboarding", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["created"] == 0
    assert len(list(db_session.scalars(select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)).all())) == len(objects)


def test_list_filters_and_verified_edit_keeps_audit_history(client, db_session, auth_headers, company):
    from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory
    from app.shared.enums import KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier
    from sqlalchemy import select

    document = Document(
        company_id=company["id"], filename="filter.docx", source_format="docx",
        status=DocumentStatus.PROCESSED, page_count=1, byte_size=20, warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    onboard = KnowledgeObject(
        company_id=company["id"], type="terminology", tier=KnowledgeTier.COMPANY,
        status=KnowledgeStatus.PROPOSED, label="Onboard term", payload={"canonicalKey": "onboarding:terminology_text:onboard term"},
        source_kind=KnowledgeSourceKind.ONBOARDING, source_document_id=None,
        source_location="onboarding.terminology_text", extraction_method="onboarding-profile",
        extracted_at=datetime.now(UTC),
    )
    doc_item = KnowledgeObject(
        company_id=company["id"], type="business_rule", tier=KnowledgeTier.COMPANY,
        status=KnowledgeStatus.PROPOSED, label="Doc rule", payload={"evidence": [{"documentId": str(document.id), "documentName": "filter.docx"}]},
        source_kind=KnowledgeSourceKind.UPLOADED_DOCUMENT, source_document_id=document.id,
        source_location="Rules", extraction_method="deterministic", extracted_at=datetime.now(UTC),
    )
    db_session.add_all([onboard, doc_item])
    db_session.flush()

    origin = client.get(
        f"/api/v1/companies/{company['id']}/knowledge-objects?origin=onboarding",
        headers=auth_headers,
    )
    assert origin.status_code == 200
    assert origin.json()["total"] == 1
    assert origin.json()["items"][0]["sourceKind"] == "onboarding"

    by_type = client.get(
        f"/api/v1/companies/{company['id']}/knowledge-objects?type=business_rule&source_kind=uploaded_document",
        headers=auth_headers,
    )
    assert by_type.json()["total"] == 1

    confirmed = client.post(
        f"/api/v1/companies/{company['id']}/knowledge-objects/{doc_item.id}/confirm",
        headers=auth_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["verifiedBy"] is not None
    evidence_before = confirmed.json()["payload"]["evidence"]

    edited = client.patch(
        f"/api/v1/companies/{company['id']}/knowledge-objects/{doc_item.id}",
        headers=auth_headers,
        json={"label": "Doc rule revised"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "proposed"
    assert edited.json()["sourceKind"] == "human_created"
    assert edited.json()["supersedesId"] == str(doc_item.id)
    assert edited.json()["payload"]["evidence"] == evidence_before
    assert edited.json()["version"] == 2

    db_session.refresh(doc_item)
    assert doc_item.status == KnowledgeStatus.SUPERSEDED

    history = client.get(
        f"/api/v1/companies/{company['id']}/knowledge-objects/{edited.json()['id']}/history",
        headers=auth_headers,
    )
    assert history.status_code == 200
    actions = {row["action"] for row in history.json()}
    assert "confirmed" in actions or "superseded" in actions
    assert "proposed_created" in actions
    assert any(row["evidenceSnapshot"] for row in history.json())

    rejected = client.post(
        f"/api/v1/companies/{company['id']}/knowledge-objects/{onboard.id}/reject",
        headers=auth_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["rejectedBy"] is not None
    assert rejected.json()["rejectedAt"] is not None


def test_knowledge_filters_preserve_company_isolation_on_history(client, auth_headers, company, user_factory, db_session):
    document = Document(
        company_id=company["id"], filename="iso.docx", source_format="docx",
        status=DocumentStatus.PROCESSED, page_count=1, byte_size=10, warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    item = KnowledgeObject(
        company_id=company["id"], type="role", tier=KnowledgeTier.COMPANY,
        status=KnowledgeStatus.PROPOSED, label="Isolated", payload={},
        source_kind=KnowledgeSourceKind.UPLOADED_DOCUMENT, source_document_id=document.id,
        source_location="Roles", extraction_method="test-fixture", extracted_at=datetime.now(UTC),
    )
    db_session.add(item)
    db_session.flush()
    other = user_factory()
    assert client.get(
        f"/api/v1/companies/{company['id']}/knowledge-objects/{item.id}/history",
        headers=other,
    ).status_code == 404
