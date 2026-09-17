import uuid
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.shared.enums import DocumentStatus, KnowledgeTier
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.errors import LLMError
from app.modules.documents.models import Document, DocumentChunk
from app.processing.chunker import chunk_document
from app.processing.extractor import UnsupportedDocumentError, extract
from app.modules.documents.cancellation import OperationCancelled, check_cancelled

EMBED_BATCH = 32


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
        check_cancelled(cancel_token)
        report("extracting", 42)
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

        # A scanned document is stored and visibly flagged rather than silently
        # producing a handful of misleading chunks.
        if extracted.is_probably_scanned:
            document.status = DocumentStatus.NEEDS_OCR
            self.db.flush()
            return document

        report("structuring", 68)
        chunks = chunk_document(extracted)
        check_cancelled(cancel_token)
        report("structuring", 80)
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
                self._embed(semantic_rows, cancel_token)
                report("embedding", 95)
            except OperationCancelled:
                for row in rows:
                    self.db.delete(row)
                document.status = DocumentStatus.CANCELLED
                self.db.flush()
                return document
            except LLMError as exc:
                # Chunks are still useful without vectors; the failure is
                # recorded rather than hidden, and re-embedding can retry.
                document.warnings = [*document.warnings, f"Embedding failed: {exc}"]

        report("finalizing", 97)
        document.status = DocumentStatus.PROCESSED
        self.db.flush()
        report("completed", 100)
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

    def _embed(self, rows: list[DocumentChunk], cancel_token: threading.Event | None = None) -> None:
        for start in range(0, len(rows), EMBED_BATCH):
            check_cancelled(cancel_token)
            batch = rows[start : start + EMBED_BATCH]
            vectors = self.llm.embed([self.embedding_text(row) for row in batch])
            check_cancelled(cancel_token)
            for row, vector in zip(batch, vectors, strict=True):
                row.embedding = vector
                row.embedding_model = self.llm.embedding_model
        self.db.flush()
