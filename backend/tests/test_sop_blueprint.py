"""SOP project + verified CKM blueprint mapping. Does not generate SOP prose."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.dependencies import require_ai_ready
from app.integrations.llm.base import Completion
from app.modules.auth.models import UserCompanyAccess
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.generation_context import build_generation_context_service
from app.modules.knowledge.models import KnowledgeObject
from app.modules.sops.dependencies import get_sop_project_service
from app.modules.sops.repository import SopProjectRepository
from app.modules.sops.schemas import SopProjectCreate
from app.modules.sops.service import SopProjectService
from app.shared.enums import DocumentKind, DocumentStatus, KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier

QUERY = "Training and Retraining of GxP Personnel"
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
        return Completion(text="This shall never become SOP prose.", model=self.chat_model, provider=self.name)

    def embed(self, texts, *, task="document"):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if any(token in lowered for token in ("training", "retrain", "gxp", "personnel")):
                vectors.append(_topic_vector())
            else:
                vectors.append(_other_vector())
        return vectors


def _cid(company) -> uuid.UUID:
    value = company["id"] if isinstance(company, dict) else company
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _document(db_session, company_id, filename="SOP-HR-001.docx", kind=DocumentKind.SOP) -> Document:
    document = Document(
        company_id=company_id,
        filename=filename,
        source_format="docx",
        status=DocumentStatus.PROCESSED,
        kind=kind,
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
    payload=None,
    source_location=None,
) -> KnowledgeObject:
    item = KnowledgeObject(
        company_id=company_id,
        type=type,
        tier=KnowledgeTier.COMPANY,
        status=status,
        label=label,
        payload=payload
        or {
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
        source_location=source_location or " > ".join(chunk.heading_path),
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


def _service(db_session) -> SopProjectService:
    companies = CompanyService(db_session, CompanyRepository(db_session))
    llm = _FakeEmbedder()
    return SopProjectService(
        db_session,
        companies,
        SopProjectRepository(db_session),
        build_generation_context_service(db_session, companies, llm),
        llm,
    )


def _training_doc(db_session, company_id):
    document = _document(db_session, company_id)
    headings = [
        (0, ["PURPOSE"], "This SOP describes training and retraining of GxP personnel."),
        (1, ["REFERENCES"], "EU GMP and ICH Q10 apply to personnel training."),
        (2, ["RESPONSIBILITIES"], "QA owns the GxP training programme."),
        (3, ["SOP TRAINING AND INTENDED USERS"], "All GxP personnel must read this SOP."),
        (4, ["DEFINITION AND ABBREVIATIONS"], "GxP means GMP, GDP, GCP as applicable."),
        (5, ["GENERAL"], "Training and re-training may apply to production tasks."),
        (6, ["PROCEDURE"], "GxP refresh training is provided at least annually."),
        (7, ["RECORDS"], "Training records are retained by HR."),
    ]
    chunks = []
    for order, path, text in headings:
        vector = _topic_vector() if "train" in text.lower() or "gxp" in text.lower() else _other_vector()
        chunks.append(_chunk(db_session, document, order=order, path=path, text=text, vector=vector))
    return document, chunks


def test_blueprint_uses_verified_structure_and_excludes_untrusted(
    db_session, company, auth_headers
):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    user_id = access.user_id
    document, chunks = _training_doc(db_session, company_id)
    purpose, _refs, _resp, _users, defs, general, procedure, records = chunks

    structure = _ko(
        db_session,
        company_id,
        document,
        purpose,
        label="SOP-HR-001 structure",
        status=KnowledgeStatus.VERIFIED,
        type="document_structure",
        user_id=user_id,
        payload={
            "headingPaths": [
                ["PURPOSE"],
                ["REFERENCES"],
                ["RESPONSIBILITIES"],
                ["SOP TRAINING AND INTENDED USERS"],
                ["DEFINITION AND ABBREVIATIONS"],
                ["GENERAL"],
                ["PROCEDURE"],
                ["RECORDS"],
            ]
        },
        source_location="document",
    )
    term = _ko(
        db_session,
        company_id,
        document,
        defs,
        label="GxP personnel",
        status=KnowledgeStatus.VERIFIED,
        type="terminology",
        user_id=user_id,
        source_location="DEFINITION AND ABBREVIATIONS",
    )
    role = _ko(
        db_session,
        company_id,
        document,
        general,
        label="QA owns GxP training",
        status=KnowledgeStatus.VERIFIED,
        type="role",
        user_id=user_id,
        source_location="RESPONSIBILITIES",
    )
    rule = _ko(
        db_session,
        company_id,
        document,
        procedure,
        label="GxP personnel must complete training and retraining annually",
        status=KnowledgeStatus.VERIFIED,
        type="business_rule",
        user_id=user_id,
        source_location="PROCEDURE",
    )
    form = _ko(
        db_session,
        company_id,
        document,
        records,
        label="Training attendance records are retained by HR",
        status=KnowledgeStatus.VERIFIED,
        type="form_or_record",
        user_id=user_id,
        source_location="RECORDS",
    )
    proposed = _ko(
        db_session,
        company_id,
        document,
        procedure,
        label="Proposed undocumented trainer qualification",
        status=KnowledgeStatus.PROPOSED,
        type="business_rule",
    )
    rejected = _ko(
        db_session,
        company_id,
        document,
        procedure,
        label="Rejected verbal-only retraining",
        status=KnowledgeStatus.REJECTED,
        type="workflow",
        user_id=user_id,
    )
    superseded = _ko(
        db_session,
        company_id,
        document,
        procedure,
        label="Superseded training interval v1",
        status=KnowledgeStatus.SUPERSEDED,
        type="business_rule",
        user_id=user_id,
    )
    _ko(
        db_session,
        company_id,
        document,
        procedure,
        label="Current training interval v2",
        status=KnowledgeStatus.VERIFIED,
        type="business_rule",
        user_id=user_id,
        version=2,
        supersedes_id=superseded.id,
        source_location="PROCEDURE",
    )
    style = _ko(
        db_session,
        company_id,
        document,
        purpose,
        label="Use formal third person",
        status=KnowledgeStatus.VERIFIED,
        type="writing_style",
        user_id=user_id,
        payload={"scope": "document"},
        source_location="document",
    )

    service = _service(db_session)
    project = service.create(
        user_id,
        company_id,
        SopProjectCreate(title=QUERY, topic=QUERY),
    )
    assert project.status == "planning"
    assert project.blueprint is None

    project = service.build_blueprint(user_id, company_id, project.id)
    assert project.status == "blueprint_ready"
    assert project.blueprint_version == 1
    blueprint = project.blueprint
    assert blueprint["structureSource"] == "verified_document_structure"
    assert blueprint["summary"]["fallbackStructure"] is False
    headings = [section["heading"] for section in blueprint["sections"]]
    assert headings[0] == "PURPOSE"
    assert "PROCEDURE" in headings
    assert str(structure.id) not in {
        kid for section in blueprint["sections"] for kid in section["knowledgeObjectIds"]
    }

    ids = {kid for section in blueprint["sections"] for kid in section["knowledgeObjectIds"]}
    evidence_ids = {row["id"] for section in blueprint["sections"] for row in section["evidence"] if row["kind"] == "verified_knowledge"}
    assert str(term.id) in ids
    assert str(role.id) in ids
    assert str(rule.id) in ids
    assert str(form.id) in ids
    assert str(proposed.id) not in ids
    assert str(rejected.id) not in ids
    assert str(superseded.id) not in ids
    assert str(style.id) not in ids
    assert any(item["id"] == str(style.id) for item in blueprint["generationGuidance"])

    by_key = {section["sectionKey"]: section for section in blueprint["sections"]}
    assert str(term.id) in by_key["definition_and_abbreviations"]["knowledgeObjectIds"]
    assert str(role.id) in by_key["responsibilities"]["knowledgeObjectIds"]
    assert any(str(rule.id) in by_key[key]["knowledgeObjectIds"] for key in ("procedure", "general"))
    assert str(form.id) in by_key["records"]["knowledgeObjectIds"]
    cited = next(row for row in by_key["definition_and_abbreviations"]["evidence"] if row["id"] == str(term.id))
    assert cited["sourceDocumentId"] == str(document.id)
    assert cited["sourceChunkId"] == str(defs.id)
    assert cited["status"] == "verified"
    assert cited["snippet"]

    chunk_evidence = [row for section in blueprint["sections"] for row in section["evidence"] if row["kind"] == "source_chunk"]
    assert chunk_evidence
    assert all(row["status"] == "source_evidence" for row in chunk_evidence)

    statuses = {section["generationStatus"] for section in blueprint["sections"]}
    assert "grounded" in statuses or "partial" in statuses
    assert by_key["records"]["generationStatus"] in {"grounded", "partial"}
    assert all("shall the operator" not in section["objective"].lower() for section in blueprint["sections"])
    assert all(len(section["objective"]) < 1200 for section in blueprint["sections"])

    project = service.build_blueprint(user_id, company_id, project.id)
    assert project.blueprint_version == 2
    ready = service.mark_generation_ready(user_id, company_id, project.id)
    assert ready.status == "generation_ready"
    assert evidence_ids


def test_blueprint_falls_back_when_no_company_structure(db_session, company, auth_headers):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    service = _service(db_session)
    project = service.create(access.user_id, company_id, SopProjectCreate(title=QUERY, topic=QUERY))
    project = service.build_blueprint(access.user_id, company_id, project.id)
    blueprint = project.blueprint
    assert blueprint["structureSource"] == "generic_fallback"
    assert blueprint["summary"]["fallbackStructure"] is True
    assert blueprint["summary"]["verifiedPoolSize"] == 0
    headings = [section["heading"] for section in blueprint["sections"]]
    assert headings == [
        "PURPOSE",
        "REFERENCES",
        "RESPONSIBILITIES",
        "SOP TRAINING AND INTENDED USERS",
        "DEFINITION AND ABBREVIATIONS",
        "GENERAL",
        "PROCEDURE",
        "RECORDS",
        "APPENDICES",
        "SOP CHANGES",
    ]
    required = [section for section in blueprint["sections"] if section["heading"] in {"PURPOSE", "RESPONSIBILITIES", "PROCEDURE", "RECORDS"}]
    assert all(section["generationStatus"] == "blocked" for section in required)
    assert all(section["knowledgeObjectIds"] == [] for section in blueprint["sections"])
    assert any("No verified company" in gap["reason"] for section in required for gap in section["gaps"])


def test_blueprint_uses_uploaded_sop_outline_without_promoting_chunks(
    db_session, company, auth_headers
):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    _training_doc(db_session, company_id)
    service = _service(db_session)
    project = service.create(access.user_id, company_id, SopProjectCreate(title=QUERY, topic=QUERY))
    project = service.build_blueprint(access.user_id, company_id, project.id)
    blueprint = project.blueprint
    assert blueprint["structureSource"] == "uploaded_sop_structure"
    assert "verified company facts" in blueprint["structureSourceNote"].lower() or "not verified" in blueprint["structureSourceNote"].lower()
    assert "PURPOSE" in [section["heading"] for section in blueprint["sections"]]
    assert all(section["knowledgeObjectIds"] == [] for section in blueprint["sections"])
    procedure = next(section for section in blueprint["sections"] if section["heading"] == "PROCEDURE")
    assert procedure["sourceChunkIds"]
    assert procedure["generationStatus"] == "blocked"
    assert any(row["kind"] == "source_chunk" for row in procedure["evidence"])
    assert any(gap["field"] == "unverified_source_evidence" for gap in procedure["gaps"])


def test_sop_projects_are_company_isolated(client, db_session, auth_headers, company, user_factory):
    company_id = _cid(company)
    access = db_session.scalar(select(UserCompanyAccess).where(UserCompanyAccess.company_id == company_id))
    service = _service(db_session)
    project = service.create(access.user_id, company_id, SopProjectCreate(title=QUERY, topic=QUERY))
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

    client.app.dependency_overrides[require_ai_ready] = lambda: None
    client.app.dependency_overrides[get_sop_project_service] = lambda: service

    denied = client.get(
        f"/api/v1/companies/{company_id}/sop-projects/{project.id}",
        headers=other,
    )
    assert denied.status_code == 404
    leaked = client.get(
        f"/api/v1/companies/{other_company_id}/sop-projects/{project.id}",
        headers=auth_headers,
    )
    assert leaked.status_code == 404
    created = client.post(
        f"/api/v1/companies/{company_id}/sop-projects",
        headers=auth_headers,
        json={"title": QUERY, "topic": QUERY},
    )
    assert created.status_code == 201
    built = client.post(
        f"/api/v1/companies/{company_id}/sop-projects/{created.json()['id']}/blueprint",
        headers=auth_headers,
        json={},
    )
    assert built.status_code == 200
    body = built.json()
    assert body["blueprint"]["structureSource"] in {
        "verified_document_structure",
        "uploaded_sop_structure",
        "generic_fallback",
    }
    assert "sop body" not in str(body).lower()
    foreign = client.post(
        f"/api/v1/companies/{other_company_id}/sop-projects/{created.json()['id']}/blueprint",
        headers=auth_headers,
        json={},
    )
    assert foreign.status_code == 404
