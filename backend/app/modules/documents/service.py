import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.shared.enums import DocumentStatus
from app.modules.documents.models import Document, DocumentChunk
from app.modules.documents.schemas import CompanyStats
from app.modules.companies.service import CompanyService
from app.modules.companies.models import Company
from app.modules.knowledge.models import KnowledgeObject
from app.shared.enums import KnowledgeStatus
from app.modules.documents.cancellation import operations

class DocumentService:
    """
    Document storage and dashboard counters.

    Every method resolves the company through `CompanyService` first, so a user
    can only reach documents belonging to a company they have access to.
    """

    def __init__(self, db: Session, companies: CompanyService) -> None:
        self.db = db
        self.companies = companies

    def list(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        self.companies.get(user_id, company_id)  # raises 404 if not accessible
        base = select(Document).where(Document.company_id == company_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        page = base.order_by(Document.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(page).all()), int(total or 0)

    def get(self, user_id: uuid.UUID, company_id: uuid.UUID, document_id: uuid.UUID) -> Document:
        self.companies.get(user_id, company_id)
        document = self.db.scalars(
            select(Document).where(
                Document.id == document_id, Document.company_id == company_id
            )
        ).one_or_none()
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    def chunks(
        self, user_id: uuid.UUID, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentChunk]:
        self.get(user_id, company_id, document_id)
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_order)
        )
        return list(self.db.scalars(stmt).all())

    def delete(self, user_id: uuid.UUID, company_id: uuid.UUID, document_id: uuid.UUID) -> None:
        self.companies.get(user_id, company_id)
        document = self.db.scalar(select(Document).where(
            Document.id == document_id, Document.company_id == company_id
        ))
        if document is None:
            return  # idempotent without revealing another tenant's records
        verified_count = self._verified_dependency_count(company_id, document_id)
        if verified_count:
            raise ConflictError(
                "This SOP is referenced by verified company knowledge and cannot be deleted yet.",
                details={
                    "reason": "verified_knowledge_dependency",
                    "verifiedDependencyCount": verified_count,
                },
            )
        operations.cancel_document(document_id)
        unverified = list(self.db.scalars(select(KnowledgeObject).where(
            KnowledgeObject.company_id == company_id,
            KnowledgeObject.source_document_id == document_id,
            KnowledgeObject.status.notin_([KnowledgeStatus.VERIFIED, KnowledgeStatus.SUPERSEDED]),
        )).all())
        for item in unverified:
            self.db.delete(item)
        self.db.delete(document)
        self.db.flush()

    def _verified_dependency_count(self, company_id: uuid.UUID, document_id: uuid.UUID) -> int:
        """Count verified/superseded Knowledge Objects that depend on this document."""
        document_key = str(document_id)
        rows = list(self.db.scalars(select(KnowledgeObject).where(
            KnowledgeObject.company_id == company_id,
            KnowledgeObject.status.in_([KnowledgeStatus.VERIFIED, KnowledgeStatus.SUPERSEDED]),
        )).all())
        count = 0
        for row in rows:
            if row.source_document_id == document_id:
                count += 1
                continue
            evidence = row.payload.get("evidence") if isinstance(row.payload, dict) else None
            if isinstance(evidence, list) and any(
                isinstance(entry, dict) and entry.get("documentId") == document_key
                for entry in evidence
            ):
                count += 1
        return count

    def counts(self, document_id: uuid.UUID) -> tuple[int, int, int]:
        total = self.db.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        )
        embedded = self.db.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.embedding.is_not(None),
            )
        )
        semantic = self.db.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                func.coalesce(DocumentChunk.extra["isSemantic"].astext, "true") == "true",
            )
        )
        return int(total or 0), int(semantic or 0), int(embedded or 0)

    def sync_company_count(self, company_id: uuid.UUID) -> None:
        company = self.db.get(Company, company_id)
        if company:
            company.sop_count = int(self.db.scalar(select(func.count()).select_from(Document).where(
                Document.company_id == company_id
            )) or 0)

    def stats(self, user_id: uuid.UUID, company_id: uuid.UUID) -> CompanyStats:
        self.companies.get(user_id, company_id)

        def count_where(*conditions) -> int:
            stmt = select(func.count()).select_from(Document).where(
                Document.company_id == company_id, *conditions
            )
            return int(self.db.scalar(stmt) or 0)

        chunk_total = int(
            self.db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.company_id == company_id
                )
            )
            or 0
        )
        chunk_embedded = int(
            self.db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.company_id == company_id,
                    DocumentChunk.embedding.is_not(None),
                )
            )
            or 0
        )
        total_bytes = int(
            self.db.scalar(
                select(func.coalesce(func.sum(Document.byte_size), 0)).where(
                    Document.company_id == company_id
                )
            )
            or 0
        )

        return CompanyStats(
            company_id=company_id,
            document_count=count_where(),
            processed_count=count_where(Document.status == DocumentStatus.PROCESSED),
            needs_ocr_count=count_where(Document.status == DocumentStatus.NEEDS_OCR),
            failed_count=count_where(Document.status == DocumentStatus.FAILED),
            chunk_count=chunk_total,
            total_bytes=total_bytes,
            ai_features_enabled=get_settings().ai_features_enabled,
            embedded_chunk_count=chunk_embedded,
        )
