"""CKM human-review lifecycle: confirm, reject, proposed edit, verified edit, isolation."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.modules.auth.models import UserCompanyAccess
from app.modules.documents.models import Document
from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory
from app.shared.enums import DocumentStatus, KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier


def _seed_ai_object(db_session, company_id, document, *, label: str, type: str = "role") -> KnowledgeObject:
    evidence = [
        {
            "documentId": str(document.id),
            "documentName": document.filename,
            "section": ["RESPONSIBILITIES"],
            "snippet": label,
            "chunkId": "chunk-1",
        }
    ]
    item = KnowledgeObject(
        company_id=company_id,
        type=type,
        tier=KnowledgeTier.COMPANY,
        status=KnowledgeStatus.PROPOSED,
        label=label,
        payload={"evidence": evidence},
        source_kind=KnowledgeSourceKind.AI_EXTRACTED,
        source_document_id=document.id,
        source_location="RESPONSIBILITIES",
        extraction_method="local-llm-document",
        model_name="gemini-2.5-flash",
        model_provider="gemini",
        extracted_at=datetime.now(UTC),
    )
    db_session.add(item)
    db_session.flush()
    db_session.add(
        KnowledgeObjectHistory(
            company_id=company_id,
            knowledge_object_id=item.id,
            action="proposed_created",
            actor_id=None,
            label=label,
            status=KnowledgeStatus.PROPOSED,
            source_kind=KnowledgeSourceKind.AI_EXTRACTED,
            version=1,
            evidence_snapshot=evidence,
            payload_snapshot={"evidence": evidence},
            detail="local-llm-document",
        )
    )
    db_session.flush()
    return item


def _document(db_session, company_id) -> Document:
    document = Document(
        company_id=company_id,
        filename="SOP-HR-001.docx",
        source_format="docx",
        status=DocumentStatus.PROCESSED,
        page_count=1,
        byte_size=20,
        warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    return document


def test_confirm_reject_proposed_edit_and_verified_edit_lifecycle(
    client, db_session, auth_headers, company
):
    user_id = client.get("/api/v1/auth/me", headers=auth_headers).json()["id"]
    document = _document(db_session, company["id"])
    to_confirm = _seed_ai_object(db_session, company["id"], document, label="Manager Pharmaceutical Operations")
    to_reject = _seed_ai_object(
        db_session, company["id"], document, label="Training workflow", type="workflow"
    )
    to_edit = _seed_ai_object(
        db_session,
        company["id"],
        document,
        label="Personnel must sign for understanding and application of SOP",
        type="business_rule",
    )
    evidence_confirm = to_confirm.payload["evidence"]
    evidence_edit = to_edit.payload["evidence"]
    prefix = f"/api/v1/companies/{company['id']}/knowledge-objects"

    confirmed = client.post(f"{prefix}/{to_confirm.id}/confirm", headers=auth_headers)
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "verified"
    assert body["verifiedBy"] == user_id
    assert body["verifiedAt"]
    assert body["payload"]["evidence"] == evidence_confirm
    assert body["companyId"] == str(company["id"])
    assert body["sourceKind"] == "ai_extracted"
    assert body["sourceLocation"] == "RESPONSIBILITIES"
    history = client.get(f"{prefix}/{to_confirm.id}/history", headers=auth_headers).json()
    assert [row["action"] for row in history] == ["proposed_created", "confirmed"]
    assert history[-1]["actorId"] == user_id
    assert history[-1]["status"] == "verified"

    rejected = client.post(f"{prefix}/{to_reject.id}/reject", headers=auth_headers)
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["rejectedBy"] == user_id
    assert body["rejectedAt"]
    listed = client.get(f"{prefix}?include_superseded=true&limit=50", headers=auth_headers)
    assert listed.headers.get("cache-control") == "no-store"
    ids = {item["id"] for item in listed.json()["items"]}
    assert str(to_reject.id) in ids
    still = next(item for item in listed.json()["items"] if item["id"] == str(to_reject.id))
    assert still["status"] == "rejected"
    history = client.get(f"{prefix}/{to_reject.id}/history", headers=auth_headers).json()
    assert [row["action"] for row in history] == ["proposed_created", "rejected"]
    assert history[-1]["actorId"] == user_id

    new_label = "Personnel must sign that they understand and will apply this SOP"
    edited = client.patch(f"{prefix}/{to_edit.id}", headers=auth_headers, json={"label": new_label})
    assert edited.status_code == 200
    body = edited.json()
    assert body["id"] == str(to_edit.id)
    assert body["status"] == "proposed"
    assert body["label"] == new_label
    assert body["payload"]["evidence"] == evidence_edit
    assert body["sourceKind"] == "ai_extracted"
    assert body["sourceLocation"] == "RESPONSIBILITIES"
    history = client.get(f"{prefix}/{to_edit.id}/history", headers=auth_headers).json()
    assert [row["action"] for row in history] == ["proposed_created", "edited"]
    assert "Personnel must sign for understanding" in (history[-1]["detail"] or "")
    assert new_label in (history[-1]["detail"] or "")
    reloaded = client.get(f"{prefix}?limit=50", headers=auth_headers).json()
    again = next(item for item in reloaded["items"] if item["id"] == str(to_edit.id))
    assert again["label"] == new_label
    assert again["status"] == "proposed"

    revision = client.patch(
        f"{prefix}/{to_confirm.id}",
        headers=auth_headers,
        json={"label": "Head of Pharmaceutical Operations"},
    )
    assert revision.status_code == 200
    body = revision.json()
    assert body["id"] != str(to_confirm.id)
    assert body["status"] == "proposed"
    assert body["supersedesId"] == str(to_confirm.id)
    assert body["payload"]["evidence"] == evidence_confirm
    assert body["sourceLocation"] == "RESPONSIBILITIES"
    assert body["sourceDocumentId"] == str(document.id)
    assert body["version"] == 2
    db_session.refresh(to_confirm)
    assert to_confirm.status == KnowledgeStatus.SUPERSEDED
    assert to_confirm.label == "Manager Pharmaceutical Operations"
    listed = client.get(f"{prefix}?include_superseded=true&limit=50", headers=auth_headers).json()
    old = next(item for item in listed["items"] if item["id"] == str(to_confirm.id))
    assert old["status"] == "superseded"
    history = client.get(f"{prefix}/{body['id']}/history", headers=auth_headers).json()
    actions = [row["action"] for row in history]
    assert "confirmed" in actions
    assert "superseded" in actions
    assert "proposed_created" in actions
    assert any(row["evidenceSnapshot"] == evidence_confirm for row in history)


def test_review_actions_are_company_isolated(
    client, db_session, auth_headers, company, user_factory
):
    document = _document(db_session, company["id"])
    item = _seed_ai_object(db_session, company["id"], document, label="Isolated role")
    other = user_factory()
    prefix = f"/api/v1/companies/{company['id']}/knowledge-objects"
    assert client.get(prefix, headers=other).status_code == 404
    assert client.post(f"{prefix}/{item.id}/confirm", headers=other).status_code == 404
    assert client.post(f"{prefix}/{item.id}/reject", headers=other).status_code == 404
    assert client.patch(f"{prefix}/{item.id}", headers=other, json={"label": "x"}).status_code == 404
    assert client.get(f"{prefix}/{item.id}/history", headers=other).status_code == 404

    outsider_company = client.post(
        "/api/v1/companies",
        headers=other,
        json={
            "name": "Other Co",
            "industryKey": "pharma",
            "locationKey": "vienna-at",
            "regulationIds": ["eu-gmp"],
        },
    )
    assert outsider_company.status_code == 201
    outsider_id = outsider_company.json()["id"]
    assert client.post(
        f"/api/v1/companies/{outsider_id}/knowledge-objects/{item.id}/confirm",
        headers=other,
    ).status_code == 404
    assert client.patch(
        f"/api/v1/companies/{outsider_id}/knowledge-objects/{item.id}",
        headers=other,
        json={"label": "x"},
    ).status_code == 404

    db_session.refresh(item)
    assert item.status == KnowledgeStatus.PROPOSED
    assert item.label == "Isolated role"
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company["id"]))
    assert access is not None
    assert str(item.company_id) == str(company["id"])
