import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import company_id_var, get_logger, log_event
from app.shared.enums import DocumentStatus
from app.modules.documents.models import Document, DocumentChunk
from app.modules.documents.schemas import CompanyStats
from app.modules.companies.service import CompanyService
from app.modules.companies.models import Company
from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory
from app.shared.enums import KnowledgeStatus, KnowledgeSourceKind
from app.modules.documents.cancellation import operations

logger = get_logger("app.documents.delete")

_PROTECTED_STATUSES = frozenset({KnowledgeStatus.VERIFIED, KnowledgeStatus.SUPERSEDED})


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
        """
        Permanently remove a tenant-scoped document and safe derived data.

        Verified/superseded Knowledge Objects that depend on this document block
        deletion (409). Multi-source proposed/rejected objects keep remaining
        evidence after this document's provenance is stripped.
        """
        self.companies.get(user_id, company_id)
        company_id_var.set(str(company_id))
        started = time.perf_counter()
        document = self.db.scalar(
            select(Document).where(
                Document.id == document_id, Document.company_id == company_id
            )
        )
        if document is None:
            # Idempotent: do not reveal whether another tenant owns the id.
            log_event(
                logger,
                "document_delete_completed",
                "Document already absent (idempotent delete)",
                company_id=str(company_id),
                document_id=str(document_id),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            return

        filename = document.filename
        log_event(
            logger,
            "document_delete_requested",
            f"Document delete requested: {filename}",
            company_id=str(company_id),
            document_id=str(document_id),
            filename=filename,
            status=document.status,
        )

        verified_count = self._verified_dependency_count(company_id, document_id)
        if verified_count:
            log_event(
                logger,
                "document_delete_dependency_conflict",
                "Verified knowledge blocks document delete",
                level=30,
                company_id=str(company_id),
                document_id=str(document_id),
                filename=filename,
                verified_dependency_count=verified_count,
            )
            raise ConflictError(
                "This SOP is referenced by verified company knowledge and cannot be deleted yet.",
                details={
                    "reason": "verified_knowledge_dependency",
                    "verifiedDependencyCount": verified_count,
                },
            )

        # Stop cooperative in-process ingestion from writing further stages.
        operations.cancel_document(document_id)

        chunk_ids = list(
            self.db.scalars(
                select(DocumentChunk.id).where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.company_id == company_id,
                )
            ).all()
        )
        chunk_count = len(chunk_ids)
        embedding_count = int(
            self.db.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.company_id == company_id,
                    DocumentChunk.embedding.is_not(None),
                )
            )
            or 0
        )

        log_event(
            logger,
            "document_delete_started",
            "Document delete started",
            company_id=str(company_id),
            document_id=str(document_id),
            filename=filename,
            chunk_count=chunk_count,
            embedding_count=embedding_count,
        )

        try:
            evidence_removed, proposed_deleted = self._cleanup_knowledge_for_document(
                company_id=company_id,
                document_id=document_id,
                chunk_ids=chunk_ids,
                actor_id=user_id,
            )

            # Explicitly clear vectors before row removal so pgvector storage is
            # not left with orphaned values if an ORM cascade path is interrupted.
            if chunk_ids:
                chunks = list(
                    self.db.scalars(
                        select(DocumentChunk).where(
                            DocumentChunk.id.in_(chunk_ids),
                            DocumentChunk.company_id == company_id,
                        )
                    ).all()
                )
                for chunk in chunks:
                    chunk.embedding = None
                    chunk.embedding_model = None
                self.db.flush()
                log_event(
                    logger,
                    "document_embeddings_deleted",
                    "Document embeddings cleared",
                    company_id=str(company_id),
                    document_id=str(document_id),
                    embedding_count=embedding_count,
                )
                for chunk in chunks:
                    self.db.delete(chunk)
                self.db.flush()
                log_event(
                    logger,
                    "document_chunks_deleted",
                    "Document chunks deleted",
                    company_id=str(company_id),
                    document_id=str(document_id),
                    chunk_count=chunk_count,
                )

            self.db.delete(document)
            self.db.flush()
        except Exception as exc:
            log_event(
                logger,
                "document_delete_failed",
                "Document delete failed",
                level=40,
                company_id=str(company_id),
                document_id=str(document_id),
                filename=filename,
                error_type=type(exc).__name__,
                error_message=str(exc)[:300],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

        log_event(
            logger,
            "document_knowledge_evidence_removed",
            "Document evidence stripped from surviving knowledge",
            company_id=str(company_id),
            document_id=str(document_id),
            evidence_count=evidence_removed,
        )
        log_event(
            logger,
            "document_proposed_knowledge_deleted",
            "Document-derived proposed/rejected knowledge deleted",
            company_id=str(company_id),
            document_id=str(document_id),
            proposed_ko_count=proposed_deleted,
        )
        log_event(
            logger,
            "document_delete_completed",
            "Document delete completed",
            company_id=str(company_id),
            document_id=str(document_id),
            filename=filename,
            chunk_count=chunk_count,
            embedding_count=embedding_count,
            proposed_ko_count=proposed_deleted,
            evidence_count=evidence_removed,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _cleanup_knowledge_for_document(
        self,
        *,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_ids: list[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> tuple[int, int]:
        """
        Strip this document's evidence from multi-source KOs; delete single-source
        non-protected rows. Never deletes verified/superseded objects.
        """
        document_key = str(document_id)
        chunk_key_set = {str(cid) for cid in chunk_ids}
        rows = list(
            self.db.scalars(
                select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)
            ).all()
        )
        evidence_removed = 0
        proposed_deleted = 0

        for item in rows:
            if item.status in _PROTECTED_STATUSES:
                continue

            payload = dict(item.payload) if isinstance(item.payload, dict) else {}
            evidence = payload.get("evidence")
            evidence_list = evidence if isinstance(evidence, list) else []
            kept_evidence = [
                entry
                for entry in evidence_list
                if not (
                    isinstance(entry, dict)
                    and (
                        entry.get("documentId") == document_key
                        or (
                            entry.get("chunkId") is not None
                            and str(entry.get("chunkId")) in chunk_key_set
                        )
                    )
                )
            ]
            removed_here = len(evidence_list) - len(kept_evidence)
            evidence_removed += max(0, removed_here)

            hashes = payload.get("analysisHashes")
            if isinstance(hashes, dict) and document_key in hashes:
                hashes = {key: value for key, value in hashes.items() if key != document_key}
                payload["analysisHashes"] = hashes

            primary_is_this = item.source_document_id == document_id
            chunk_is_this = item.source_chunk_id is not None and item.source_chunk_id in chunk_ids

            if kept_evidence:
                payload["evidence"] = kept_evidence
                item.payload = payload
                if primary_is_this or chunk_is_this:
                    first = next((e for e in kept_evidence if isinstance(e, dict)), None)
                    if first and first.get("documentId"):
                        try:
                            item.source_document_id = uuid.UUID(str(first["documentId"]))
                        except (TypeError, ValueError):
                            item.source_document_id = None
                    else:
                        item.source_document_id = None
                    if first and first.get("chunkId"):
                        try:
                            item.source_chunk_id = uuid.UUID(str(first["chunkId"]))
                        except (TypeError, ValueError):
                            item.source_chunk_id = None
                    else:
                        item.source_chunk_id = None
                    section = first.get("section") if first else None
                    if isinstance(section, list) and section:
                        item.source_location = " > ".join(str(part) for part in section)
                    elif isinstance(section, str) and section:
                        item.source_location = section
                self.db.add(
                    KnowledgeObjectHistory(
                        company_id=company_id,
                        knowledge_object_id=item.id,
                        action="evidence_source_removed",
                        actor_id=actor_id,
                        label=item.label,
                        status=item.status,
                        source_kind=item.source_kind,
                        version=item.version,
                        evidence_snapshot=list(kept_evidence),
                        payload_snapshot=dict(payload),
                        detail=f"Removed evidence for deleted document {document_key}",
                    )
                )
                continue

            # No remaining evidence from other documents.
            if primary_is_this or chunk_is_this or removed_here:
                # Single-source (or emptied) proposed/rejected/human rows tied to
                # this document — safe to remove. Preserve onboarding-only rows
                # that never referenced this document.
                if (
                    primary_is_this
                    or chunk_is_this
                    or item.source_kind
                    in (
                        KnowledgeSourceKind.UPLOADED_DOCUMENT,
                        KnowledgeSourceKind.AI_EXTRACTED,
                    )
                ):
                    self.db.delete(item)
                    proposed_deleted += 1
                elif removed_here:
                    payload["evidence"] = []
                    item.payload = payload
            elif primary_is_this:
                self.db.delete(item)
                proposed_deleted += 1

        self.db.flush()
        return evidence_removed, proposed_deleted

    def _verified_dependency_count(self, company_id: uuid.UUID, document_id: uuid.UUID) -> int:
        """Count verified/superseded Knowledge Objects that depend on this document."""
        document_key = str(document_id)
        rows = list(
            self.db.scalars(
                select(KnowledgeObject).where(
                    KnowledgeObject.company_id == company_id,
                    KnowledgeObject.status.in_(
                        [KnowledgeStatus.VERIFIED, KnowledgeStatus.SUPERSEDED]
                    ),
                )
            ).all()
        )
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
            company.sop_count = int(
                self.db.scalar(
                    select(func.count()).select_from(Document).where(
                        Document.company_id == company_id
                    )
                )
                or 0
            )

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
