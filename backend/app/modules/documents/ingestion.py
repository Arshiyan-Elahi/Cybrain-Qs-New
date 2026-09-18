import time
import uuid
import threading
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import company_id_var, get_logger, log_event, logging_flags
from app.shared.enums import DocumentStatus, KnowledgeTier
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import LLMError
from app.modules.documents.models import Document, DocumentChunk
from app.processing.chunker import chunk_document
from app.processing.extractor import UnsupportedDocumentError, extract
from app.modules.documents.cancellation import OperationCancelled, check_cancelled

EMBED_BATCH = 32
logger = get_logger("app.documents.ingestion")


class IngestionService:
    """
    Upload -> parse -> chunk -> (optionally embed) -> store.

    Parsing, chunking and storage need no model, so document upload works with
    the AI features switched off. Embedding is skipped in that case and the
    chunks are stored without vectors; re-running ingestion later fills them in.
    """

    def __init__(self, db: Session, llm: LLMProvider | None = None) -> None:
        self.db = db
        self.llm = llm

    def ingest(
        self,
        *,
        company_id: uuid.UUID,
        filename: str,
        content: bytes,
        uploaded_by: uuid.UUID | None = None,
        tier: str = KnowledgeTier.COMPANY,
        kind: str = "general",
        embed: bool | None = None,
        cancel_token: threading.Event | None = None,
        progress: Callable[[str, int], None] | None = None,
        document_created: Callable[[uuid.UUID], None] | None = None,
    ) -> Document:
        # `embed=None` means "follow the feature flag"; an explicit value wins.
        should_embed = get_settings().ai_features_enabled if embed is None else embed
        report = progress or (lambda _stage, _value: None)
        company_id_var.set(str(company_id))
        doc_logs = logging_flags().get("log_document_processing", True)
        overall_started = time.perf_counter()
        if doc_logs:
            log_event(
                logger,
                "document_upload_received",
                f"Document upload received: {filename}",
                company_id=str(company_id),
                filename=filename,
                byte_size=len(content),
            )

        check_cancelled(cancel_token)
        report("extracting", 42)
        if doc_logs:
            log_event(
                logger,
                "extraction_started",
                "Document extraction started",
                company_id=str(company_id),
                filename=filename,
            )
        try:
            extracted = extract(content, filename)
        except UnsupportedDocumentError as exc:
            document = Document(
                company_id=company_id,
                filename=filename,
                source_format=filename.rsplit(".", 1)[-1].lower()[:16],
                status=DocumentStatus.FAILED,
                byte_size=len(content),
                warnings=[str(exc)],
                kind=kind,
                uploaded_by=uploaded_by,
            )
            self.db.add(document)
            self.db.flush()
            if doc_logs:
                log_event(
                    logger,
                    "extraction_failed",
                    "Document extraction failed",
                    level=40,
                    company_id=str(company_id),
                    document_id=str(document.id),
                    filename=filename,
                    error_message=str(exc)[:300],
                )
            return document

        check_cancelled(cancel_token)
        report("extracting", 65)
        document = Document(
            company_id=company_id,
            filename=filename,
            source_format=extracted.source_format,
            status=DocumentStatus.PROCESSING,
            page_count=extracted.page_count,
            byte_size=len(content),
            warnings=list(extracted.warnings),
            kind=kind,
            uploaded_by=uploaded_by,
        )
        self.db.add(document)
        self.db.flush()
        if document_created:
            document_created(document.id)

        if doc_logs:
            log_event(
                logger,
                "extraction_completed",
                "Document extraction completed",
                company_id=str(company_id),
                document_id=str(document.id),
                filename=filename,
                parser=getattr(extracted, "parser", None) or extracted.source_format,
                block_count=len(extracted.blocks),
                qa_status=extracted.qa_status,
                page_count=extracted.page_count,
            )
            if extracted.warnings:
                log_event(
                    logger,
                    "extraction_warning",
                    "Extraction warnings present",
                    level=30,
                    company_id=str(company_id),
                    document_id=str(document.id),
                    warning_count=len(extracted.warnings),
                )

        # A scanned document is stored and visibly flagged rather than silently
        # producing a handful of misleading chunks.
        if extracted.is_probably_scanned:
            document.status = DocumentStatus.NEEDS_OCR
            self.db.flush()
            if doc_logs:
                log_event(
                    logger,
                    "needs_ocr",
                    "Document needs OCR",
                    level=30,
                    company_id=str(company_id),
                    document_id=str(document.id),
                    filename=filename,
                )
            return document

        # Extraction QA FAILED must not silently proceed into chunking / CKM.
        if extracted.qa_status == "FAILED":
            document.status = DocumentStatus.FAILED
            self.db.flush()
            if doc_logs:
                log_event(
                    logger,
                    "extraction_failed",
                    "Extraction QA failed",
                    level=40,
                    company_id=str(company_id),
                    document_id=str(document.id),
                    filename=filename,
                    qa_status=extracted.qa_status,
                )
            return document

        report("structuring", 68)
        chunks = chunk_document(extracted)
        check_cancelled(cancel_token)
        report("structuring", 80)
        if doc_logs:
            log_event(
                logger,
                "normalization_completed",
                "Structure normalization available via extractor",
                company_id=str(company_id),
                document_id=str(document.id),
                block_count=len(extracted.blocks),
            )
            log_event(
                logger,
                "chunking_completed",
                "Chunking completed",
                company_id=str(company_id),
                document_id=str(document.id),
                chunk_count=len(chunks),
                semantic_chunk_count=sum(1 for c in chunks if c.is_semantic),
            )
        rows = [
            DocumentChunk(
                document_id=document.id,
                company_id=company_id,
                tier=tier,
                chunk_order=chunk.order,
                text=chunk.text,
                heading_path=list(chunk.heading_path),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                extra={"sectionId": chunk.section_id, "blocks": chunk.blocks,
                       "isSemantic": chunk.is_semantic},
            )
            for chunk in chunks
        ]
        self.db.add_all(rows)
        self.db.flush()

        semantic_rows = [row for row in rows if row.extra.get("isSemantic", True)]
        if should_embed and semantic_rows and self.llm is not None:
            try:
                report("embedding", 82)
                self._embed(semantic_rows, cancel_token, document_id=document.id)
                report("embedding", 95)
            except OperationCancelled:
                for row in rows:
                    self.db.delete(row)
                document.status = DocumentStatus.CANCELLED
                self.db.flush()
                if doc_logs:
                    log_event(
                        logger,
                        "document_processing_cancelled",
                        "Document processing cancelled",
                        level=30,
                        company_id=str(company_id),
                        document_id=str(document.id),
                        filename=filename,
                    )
                return document
            except LLMError as exc:
                # Chunks are still useful without vectors; the failure is
                # recorded rather than hidden, and re-embedding can retry.
                document.warnings = [*document.warnings, f"Embedding failed: {exc}"]
                if doc_logs:
                    log_event(
                        logger,
                        "extraction_warning",
                        "Embedding failed; chunks stored without vectors",
                        level=30,
                        company_id=str(company_id),
                        document_id=str(document.id),
                        error_message=str(exc)[:300],
                    )

        report("finalizing", 97)
        document.status = DocumentStatus.PROCESSED
        self.db.flush()
        report("completed", 100)
        if doc_logs:
            log_event(
                logger,
                "document_processing_completed",
                "Document processing completed",
                company_id=str(company_id),
                document_id=str(document.id),
                filename=filename,
                chunk_count=len(rows),
                latency_ms=int((time.perf_counter() - overall_started) * 1000),
            )
        return document

    @staticmethod
    def embedding_text(row: DocumentChunk) -> str:
        """
        What actually gets embedded: the heading path prepended to the body.

        A section title such as "3. Auditplanung" is often the strongest signal
        for a query, and embedding the body alone throws it away. The stored
        `text` stays clean for display and citation.
        """
        if row.heading_path:
            return " > ".join(row.heading_path) + "\n" + row.text
        return row.text

    def _embed(
        self,
        rows: list[DocumentChunk],
        cancel_token: threading.Event | None = None,
        *,
        document_id: uuid.UUID | None = None,
    ) -> None:
        doc_logs = logging_flags().get("log_document_processing", True)
        started = time.perf_counter()
        if doc_logs:
            log_event(
                logger,
                "embedding_started",
                "Document chunk embedding started",
                document_id=str(document_id) if document_id else None,
                input_count=len(rows),
                batch_size=EMBED_BATCH,
            )
        for start in range(0, len(rows), EMBED_BATCH):
            check_cancelled(cancel_token)
            batch = rows[start : start + EMBED_BATCH]
            vectors = self.llm.embed([self.embedding_text(row) for row in batch])
            check_cancelled(cancel_token)
            for row, vector in zip(batch, vectors, strict=True):
                row.embedding = vector
                row.embedding_model = self.llm.embedding_model
        self.db.flush()
        if doc_logs:
            log_event(
                logger,
                "embedding_completed",
                "Document chunk embedding completed",
                document_id=str(document_id) if document_id else None,
                input_count=len(rows),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

    def embed_missing(
        self,
        *,
        company_id: uuid.UUID,
        document_id: uuid.UUID,
        cancel_token: threading.Event | None = None,
    ) -> tuple[int, int]:
        """
        Embed semantic chunks that already exist but have NULL vectors.

        Returns (embedded_now, still_missing). Does not re-parse or re-chunk.
        """
        if self.llm is None:
            raise LLMError(
                "Embeddings require AI features to be enabled.",
                provider="none",
                reason="provider_unavailable",
                retryable=False,
            )

        rows = list(
            self.db.scalars(
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.company_id == company_id,
                    DocumentChunk.embedding.is_(None),
                )
                .order_by(DocumentChunk.chunk_order)
            ).all()
        )
        semantic_missing = [
            row for row in rows if row.extra.get("isSemantic", True)
        ]
        if not semantic_missing:
            return 0, 0

        self._embed(semantic_missing, cancel_token, document_id=document_id)

        document = self.db.get(Document, document_id)
        if document is not None:
            # Drop prior embedding-failure warnings once vectors are filled.
            document.warnings = [
                warning
                for warning in (document.warnings or [])
                if not str(warning).startswith("Embedding failed:")
            ]
            self.db.flush()

        still_missing = int(
            self.db.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.company_id == company_id,
                    DocumentChunk.embedding.is_(None),
                    func.coalesce(DocumentChunk.extra["isSemantic"].astext, "true") == "true",
                )
            )
            or 0
        )
        return len(semantic_missing), still_missing
