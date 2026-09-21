"""Verified CKM + document retrieval for SOP generation context."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.dependencies import require_ai_ready
from app.integrations.llm.base import Completion
from app.modules.auth.models import UserCompanyAccess
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.dependencies import get_generation_context_service
from app.modules.knowledge.generation_context import build_generation_context_service
from app.modules.knowledge.models import KnowledgeObject
from app.shared.enums import DocumentStatus, KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier

QUERY = "Training and retraining of GxP personnel"
DIM = 768


def _topic_vector() -> list[float]:
    vector = [0.0] * DIM
    vector[0] = 1.0
    return vector


def _other_vector() -> list[float]:
    vector = [0.0] * DIM
    vector[1] = 1.0
    return vector


class _FakeEmbedder:
    name = "fake-local"
    chat_model = "test-model"
    embedding_model = "nomic-embed-text-v1.5"
    embedding_dimensions = DIM

    def complete(self, messages, *, temperature=0.2, max_tokens=None):
        return Completion(text="[]", model=self.chat_model, provider=self.name)

    def embed(self, texts, *, task="document"):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if any(token in lowered for token in ("training", "retrain", "gxp", "personnel")):
                vectors.append(_topic_vector())
            else:
                vectors.append(_other_vector())
        return vectors


def _document(db_session, company_id, filename="SOP-HR-001.docx") -> Document:
    document = Document(
        company_id=company_id,
        filename=filename,
        source_format="docx",
        status=DocumentStatus.PROCESSED,
        page_count=1,
        byte_size=20,
        warnings=[],
    )
    db_session.add(document)
    db_session.flush()
    return document


def _chunk(db_session, document, *, order: int, path: list[str], text: str, vector: list[float]) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=document.id,
        company_id=document.company_id,
        tier=KnowledgeTier.COMPANY,
        chunk_order=order,
        heading_path=path,
        text=text,
        embedding=vector,
        embedding_model="nomic-embed-text-v1.5",
        extra={"isSemantic": True},
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk


def _ko(
    db_session,
    company_id,
    document,
    chunk,
    *,
    label: str,
    status: str,
    type: str = "business_rule",
    user_id=None,
    version: int = 1,
    supersedes_id=None,
) -> KnowledgeObject:
    item = KnowledgeObject(
        company_id=company_id,
        type=type,
        tier=KnowledgeTier.COMPANY,
        status=status,
        label=label,
        payload={
            "evidence": [
                {
                    "documentId": str(document.id),
                    "documentName": document.filename,
                    "section": chunk.heading_path,
                    "snippet": chunk.text[:200],
                    "chunkId": str(chunk.id),
                }
            ]
        },
        source_kind=KnowledgeSourceKind.AI_EXTRACTED,
        source_document_id=document.id,
        source_chunk_id=chunk.id,
        source_location=" > ".join(chunk.heading_path),
        extraction_method="local-llm-document",
        model_name="gemini-2.5-flash",
        model_provider="gemini",
        extracted_at=datetime.now(UTC),
        verified_by=user_id if status == KnowledgeStatus.VERIFIED else None,
        verified_at=datetime.now(UTC) if status == KnowledgeStatus.VERIFIED else None,
        rejected_by=user_id if status == KnowledgeStatus.REJECTED else None,
        rejected_at=datetime.now(UTC) if status == KnowledgeStatus.REJECTED else None,
        version=version,
        supersedes_id=supersedes_id,
    )
    db_session.add(item)
    db_session.flush()
    return item


def _service(db_session):
    return build_generation_context_service(
        db_session,
        CompanyService(db_session, CompanyRepository(db_session)),
        _FakeEmbedder(),
    )


def _cid(company) -> uuid.UUID:
    value = company["id"] if isinstance(company, dict) else company
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def test_trusted_retrieval_excludes_untrusted_and_keeps_current_verified(
    db_session, company, auth_headers
):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    user_id = access.user_id
    document = _document(db_session, company_id)
    training_chunk = _chunk(
        db_session,
        document,
        order=0,
        path=["GENERAL", "Training and re-training"],
        text="GxP personnel must complete training and retraining before unsupervised work.",
        vector=_topic_vector(),
    )
    supplier_chunk = _chunk(
        db_session,
        document,
        order=1,
        path=["REFERENCES"],
        text="Supplier qualification is described in a different SOP.",
        vector=_other_vector(),
    )

    verified = _ko(
        db_session,
        company_id,
        document,
        training_chunk,
        label="GxP personnel must complete training and retraining",
        status=KnowledgeStatus.VERIFIED,
        user_id=user_id,
        type="business_rule",
    )
    proposed = _ko(
        db_session,
        company_id,
        document,
        training_chunk,
        label="Proposed training coordinator role",
        status=KnowledgeStatus.PROPOSED,
        type="role",
    )
    rejected = _ko(
        db_session,
        company_id,
        document,
        training_chunk,
        label="Rejected retraining after deviation",
        status=KnowledgeStatus.REJECTED,
        user_id=user_id,
        type="workflow",
    )
    superseded = _ko(
        db_session,
        company_id,
        document,
        training_chunk,
        label="Superseded training rule v1",
        status=KnowledgeStatus.SUPERSEDED,
        user_id=user_id,
        type="business_rule",
    )
    current = _ko(
        db_session,
        company_id,
        document,
        training_chunk,
        label="Current training and retraining rule v2",
        status=KnowledgeStatus.VERIFIED,
        user_id=user_id,
        type="business_rule",
        version=2,
        supersedes_id=superseded.id,
    )
    unrelated = _ko(
        db_session,
        company_id,
        document,
        supplier_chunk,
        label="Approved supplier list must be current",
        status=KnowledgeStatus.VERIFIED,
        user_id=user_id,
        type="form_or_record",
    )

    setup_verified = db_session.scalar(
        select(func.count()).select_from(KnowledgeObject).where(
            KnowledgeObject.company_id == company_id,
            KnowledgeObject.status == KnowledgeStatus.VERIFIED.value,
        )
    )
    assert setup_verified == 3, setup_verified

    package = _service(db_session).build(user_id, company_id, QUERY)
    labels = [item.label for _kind, group in package.knowledge for item in group]
    ids = {item.id for _kind, group in package.knowledge for item in group}

    assert package.metadata.verified_pool_size == 3, (
        f"verified_pool_size={package.metadata.verified_pool_size} "
        f"knowledge_returned={package.metadata.knowledge_returned} "
        f"chunk_returned={package.metadata.chunk_returned} labels={labels}"
    )
    assert verified.label in labels
    assert current.label in labels
    assert proposed.label not in labels
    assert rejected.label not in labels
    assert superseded.label not in labels
    assert unrelated.label not in labels
    assert proposed.id not in ids
    assert rejected.id not in ids
    assert superseded.id not in ids
    assert current.id in ids
    assert verified.id in ids
    assert all(item.status == "verified" for _kind, group in package.knowledge for item in group)
    assert {kind for kind, _group in package.knowledge} == {"business_rule"}

    cited = next(item for _kind, group in package.knowledge for item in group if item.id == verified.id)
    assert cited.tier == "company"
    assert cited.version == 1
    assert cited.citation.source_document_id == document.id
    assert cited.citation.source_chunk_id == training_chunk.id
    assert cited.citation.source_location == "GENERAL > Training and re-training"
    assert cited.citation.evidence
    assert cited.citation.evidence[0]["snippet"]
    assert cited.payload["evidence"][0]["chunkId"] == str(training_chunk.id)
    assert cited.citation.verified_by == user_id

    chunk_ids = {hit.chunk_id for hit in package.source_chunks}
    assert training_chunk.id in chunk_ids
    assert package.source_chunks[0].chunk_id == training_chunk.id
    assert "training" in package.source_chunks[0].text.lower()
    assert package.company.id == company_id
    assert package.metadata.knowledge_returned == 2
    assert package.metadata.mode == "semantic"
    assert package.metadata.embedding_dimensions == DIM


def test_empty_verified_pool_excludes_proposed_and_still_returns_chunks(
    db_session, company, auth_headers
):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    document = _document(db_session, company_id)
    chunk = _chunk(
        db_session,
        document,
        order=0,
        path=["GENERAL", "Training and re-training"],
        text="GxP personnel must complete training and retraining before unsupervised work.",
        vector=_topic_vector(),
    )
    _ko(
        db_session,
        company_id,
        document,
        chunk,
        label="Proposed GxP training rule",
        status=KnowledgeStatus.PROPOSED,
    )
    package = _service(db_session).build(access.user_id, company_id, QUERY)
    assert package.metadata.verified_pool_size == 0
    assert package.knowledge == []
    assert package.notes
    assert chunk.id in {hit.chunk_id for hit in package.source_chunks}


def test_generation_context_is_company_isolated(client, db_session, auth_headers, company, user_factory):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    document = _document(db_session, company_id)
    chunk = _chunk(
        db_session,
        document,
        order=0,
        path=["PURPOSE"],
        text="Training and retraining of GxP personnel is required.",
        vector=_topic_vector(),
    )
    _ko(
        db_session,
        company_id,
        document,
        chunk,
        label="Verified training rule",
        status=KnowledgeStatus.VERIFIED,
        user_id=access.user_id,
    )

    other = user_factory()
    outsider = client.post(
        "/api/v1/companies",
        headers=other,
        json={
            "name": "Other Co",
            "industryKey": "pharma",
            "locationKey": "vienna-at",
            "regulationIds": ["eu-gmp"],
        },
    )
    assert outsider.status_code == 201
    other_company_id = outsider.json()["id"]
    other_access = db_session.scalar(
        select(UserCompanyAccess).where(UserCompanyAccess.company_id == other_company_id)
    )
    other_document = _document(db_session, other_company_id, filename="other.docx")
    other_chunk = _chunk(
        db_session,
        other_document,
        order=0,
        path=["PURPOSE"],
        text="Training and retraining of GxP personnel at the other company.",
        vector=_topic_vector(),
    )
    foreign = _ko(
        db_session,
        other_company_id,
        other_document,
        other_chunk,
        label="Other company training rule",
        status=KnowledgeStatus.VERIFIED,
        user_id=other_access.user_id,
    )

    package = _service(db_session).build(access.user_id, company_id, QUERY)
    ids = {item.id for _kind, group in package.knowledge for item in group}
    chunk_ids = {hit.chunk_id for hit in package.source_chunks}
    assert foreign.id not in ids
    assert other_chunk.id not in chunk_ids
    assert package.metadata.verified_pool_size >= 1
    assert ids
    assert all(item.citation.source_document_id == document.id for _kind, group in package.knowledge for item in group)

    service = _service(db_session)
    client.app.dependency_overrides[require_ai_ready] = lambda: None
    client.app.dependency_overrides[get_generation_context_service] = lambda: service
    denied = client.post(
        f"/api/v1/companies/{company['id']}/retrieval/preview",
        headers=other,
        json={"query": QUERY},
    )
    assert denied.status_code == 404
    leaked = client.post(
        f"/api/v1/companies/{other_company_id}/retrieval/preview",
        headers=auth_headers,
        json={"query": QUERY},
    )
    assert leaked.status_code == 404

    allowed = client.post(
        f"/api/v1/companies/{company['id']}/retrieval/preview",
        headers=auth_headers,
        json={"query": QUERY},
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["metadata"]["verifiedPoolSize"] >= 1
    assert all(item["status"] == "verified" for group in body["knowledge"] for item in group["items"])
    assert all(item["citation"]["sourceDocumentId"] != str(other_document.id) for group in body["knowledge"] for item in group["items"])
    assert {hit["chunkId"] for hit in body["sourceChunks"]} == {str(chunk.id)} or str(chunk.id) in {
        hit["chunkId"] for hit in body["sourceChunks"]
    }
