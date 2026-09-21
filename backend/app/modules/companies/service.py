import logging
import time
import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import company_id_var, log_event
from app.modules.companies.models import Company
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate
from app.modules.documents.cancellation import operations
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory
from app.modules.sops.models import SopProject

logger = logging.getLogger("app.companies.delete")

# Strongest role currently issued on create. "admin" is not used yet; do not
# invent additional RBAC beyond this stored membership role.
_COMPANY_DELETE_ROLES = frozenset({"owner"})


class CompanyService:
    def __init__(self, db: Session, repo: CompanyRepository) -> None:
        self.db = db
        self.repo = repo

    def list(
        self,
        user_id: uuid.UUID,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Company], int]:
        return self.repo.list_for_user(user_id, search, limit, offset)

    def get(self, user_id: uuid.UUID, company_id: uuid.UUID) -> Company:
        company = self.repo.get_for_user(user_id, company_id)
        if company is None:
            # Same response whether it does not exist or the user cannot see it,
            # so the endpoint cannot confirm another tenant's company exists.
            raise NotFoundError("Company not found.")
        return company

    def create(self, user_id: uuid.UUID, payload: CompanyCreate) -> Company:
        if payload.creation_request_id is not None:
            existing = self.repo.get_by_creation_request(user_id, payload.creation_request_id)
            if existing is not None:
                return existing

        data = payload.model_dump(exclude={"regulation_ids", "onboarding"})
        onboarding = (
            payload.onboarding.model_dump() if payload.onboarding is not None else None
        )
        try:
            with self.db.begin_nested():
                company = self.repo.create(data, payload.regulation_ids, onboarding)
                # The creator always gets access, otherwise they could not read it back.
                self.repo.grant_access(user_id, company.id, role="owner")
                self.db.flush()
            return company
        except IntegrityError:
            if payload.creation_request_id is None:
                raise
            existing = self.repo.get_by_creation_request(user_id, payload.creation_request_id)
            if existing is None:
                raise
            return existing

    def update(self, user_id: uuid.UUID, company_id: uuid.UUID, payload: CompanyUpdate) -> Company:
        company = self.get(user_id, company_id)
        changes = payload.model_dump(
            exclude_unset=True, exclude={"regulation_ids", "onboarding"}
        )
        for field, value in changes.items():
            setattr(company, field, value)
        if payload.regulation_ids is not None:
            self.repo.replace_regulations(company, payload.regulation_ids)
        if "onboarding" in payload.model_fields_set and payload.onboarding is not None:
            self.repo.upsert_onboarding(company, payload.onboarding.model_dump())
        self.db.flush()
        return company

    def delete(self, user_id: uuid.UUID, company_id: uuid.UUID) -> None:
        """
        Permanently delete a company and every row owned exclusively by it.

        Verified CKM does not block whole-company deletion. Requires the
        stored membership role ``owner`` (strongest role currently issued).
        """
        company = self.get(user_id, company_id)
        access = self.repo.get_access(user_id, company_id)
        if access is None or access.role not in _COMPANY_DELETE_ROLES:
            raise PermissionDeniedError(
                "Only a company owner can permanently delete this company.",
                details={"reason": "company_owner_required"},
            )

        company_id_var.set(str(company_id))
        started = time.perf_counter()

        log_event(
            logger,
            "company_delete_requested",
            "Company delete requested",
            company_id=str(company_id),
        )

        document_ids = list(
            self.db.scalars(select(Document.id).where(Document.company_id == company_id)).all()
        )
        document_count = len(document_ids)
        chunk_count = int(
            self.db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.company_id == company_id
                )
            )
            or 0
        )
        embedding_count = int(
            self.db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.company_id == company_id,
                    DocumentChunk.embedding.is_not(None),
                )
            )
            or 0
        )
        knowledge_count = int(
            self.db.scalar(
                select(func.count()).select_from(KnowledgeObject).where(
                    KnowledgeObject.company_id == company_id
                )
            )
            or 0
        )
        history_count = int(
            self.db.scalar(
                select(func.count()).select_from(KnowledgeObjectHistory).where(
                    KnowledgeObjectHistory.company_id == company_id
                )
            )
            or 0
        )

        # Stop cooperative ingestion before removing rows so stages cannot recreate them.
        operations.cancel_documents(set(document_ids))

        log_event(
            logger,
            "company_delete_started",
            "Company delete started",
            company_id=str(company_id),
            document_count=document_count,
            chunk_count=chunk_count,
            embedding_count=embedding_count,
            knowledge_count=knowledge_count,
            history_count=history_count,
        )

        try:
            self.db.execute(delete(SopProject).where(SopProject.company_id == company_id))
            self.db.flush()
            # Knowledge first: source_document_id is RESTRICT on documents.
            self.db.execute(
                delete(KnowledgeObjectHistory).where(
                    KnowledgeObjectHistory.company_id == company_id
                )
            )
            self.db.execute(
                delete(KnowledgeObject).where(KnowledgeObject.company_id == company_id)
            )
            self.db.flush()
            log_event(
                logger,
                "company_knowledge_deleted",
                "Company knowledge and history deleted",
                company_id=str(company_id),
                knowledge_count=knowledge_count,
                history_count=history_count,
            )

            if chunk_count:
                self.db.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.company_id == company_id)
                    .values(embedding=None, embedding_model=None)
                )
                self.db.flush()
                log_event(
                    logger,
                    "company_vectors_deleted",
                    "Company pgvector embeddings cleared",
                    company_id=str(company_id),
                    embedding_count=embedding_count,
                    chunk_count=chunk_count,
                )
                self.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.company_id == company_id)
                )
                self.db.flush()

            if document_count:
                self.db.execute(delete(Document).where(Document.company_id == company_id))
                self.db.flush()
            log_event(
                logger,
                "company_documents_deleted",
                "Company documents and chunks deleted",
                company_id=str(company_id),
                document_count=document_count,
                chunk_count=chunk_count,
            )

            # Cascades: onboarding profile, regulations, user_company_access.
            self.repo.delete(company)
            self.db.flush()
        except Exception as exc:
            log_event(
                logger,
                "company_delete_failed",
                "Company delete failed",
                level=40,
                company_id=str(company_id),
                error_type=type(exc).__name__,
                error_message=str(exc)[:300],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

        log_event(
            logger,
            "company_delete_completed",
            "Company delete completed",
            company_id=str(company_id),
            document_count=document_count,
            chunk_count=chunk_count,
            embedding_count=embedding_count,
            knowledge_count=knowledge_count,
            history_count=history_count,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
