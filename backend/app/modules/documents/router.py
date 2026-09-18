import uuid

from fastapi import APIRouter, File, Query, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import AppSettings
from app.core.errors import ValidationError
from app.core.pagination import Page, Paging
from app.modules.auth.dependencies import CurrentUser
from app.modules.companies.dependencies import CompanySvc
from app.modules.documents.dependencies import DocumentSvc, IngestionSvc
from app.modules.documents.models import Document
from app.modules.documents.schemas import (
    ChunkRead,
    CompanyStats,
    DocumentDetail,
    DocumentRead,
)
from app.modules.documents.cancellation import OperationCancelled, operations
from app.shared.enums import DocumentKind

router = APIRouter(prefix="/companies/{company_id}", tags=["documents"])

ALLOWED_SUFFIXES = (".pdf", ".docx")
ALLOWED_KINDS = {DocumentKind.GENERAL, DocumentKind.SOP, DocumentKind.TEMPLATE}


def _detail(service, document: Document) -> DocumentDetail:
    """Single place that assembles the detail response, previously duplicated."""
    total, semantic, embedded = service.counts(document.id)
    return DocumentDetail(
        **DocumentRead.model_validate(document).model_dump(),
        chunk_count=total,
        semantic_chunk_count=semantic,
        embedded_chunk_count=embedded,
    )


@router.post("/documents", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
async def upload_document(
    company_id: uuid.UUID,
    companies: CompanySvc,
    documents: DocumentSvc,
    ingestion: IngestionSvc,
    current_user: CurrentUser,
    settings: AppSettings,
    file: UploadFile = File(...),
    operation_id: uuid.UUID | None = None,
    kind: str = Query(default=DocumentKind.GENERAL),
):
    companies.get(current_user.id, company_id)  # 404 unless accessible

    if kind not in ALLOWED_KINDS:
        raise ValidationError(
            f"Unsupported document kind. Supported: {', '.join(sorted(ALLOWED_KINDS))}"
        )

    token = operations.token(operation_id) if operation_id else None
    if operation_id:
        operations.update(operation_id, "extracting", 40)
    content = await file.read()
    if not content:
        raise ValidationError("The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        from app.core.errors import PayloadTooLargeError

        raise PayloadTooLargeError(
            f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit."
        )

    filename = file.filename or "upload"
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        # Checked before parsing so an obviously wrong type never reaches the parser.
        raise ValidationError(
            f"Unsupported file type. Supported: {', '.join(ALLOWED_SUFFIXES)}"
        )

    # Parsing is CPU-bound and synchronous. Running it on the threadpool keeps
    # the event loop free instead of stalling every other request for the
    # duration of a large document.
    try:
        document = await run_in_threadpool(
            ingestion.ingest, company_id=company_id, filename=filename, content=content,
            uploaded_by=current_user.id, kind=kind, cancel_token=token,
            progress=(lambda stage, value: operations.update(operation_id, stage, value)) if operation_id else None,
            document_created=(lambda document_id: operations.bind_document(operation_id, document_id)) if operation_id else None,
        )
        documents.sync_company_count(company_id)
        return _detail(documents, document)
    except OperationCancelled:
        cancelled = Document(company_id=company_id, filename=filename,
            source_format=filename.rsplit(".", 1)[-1].lower(), status="cancelled",
            byte_size=len(content), warnings=["Operation cancelled by user."],
            kind=kind, uploaded_by=current_user.id)
        ingestion.db.add(cancelled)
        ingestion.db.flush()
        if operation_id:
            operations.update(operation_id, "cancelled", 0, "cancelled")
        return _detail(documents, cancelled)
    except Exception as exc:
        if operation_id:
            operations.update(operation_id, "failed", 0, "failed", str(exc))
        raise


@router.post("/operations/{operation_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_document_operation(company_id: uuid.UUID, operation_id: uuid.UUID,
                              companies: CompanySvc, current_user: CurrentUser):
    companies.get(current_user.id, company_id)
    operations.cancel(operation_id)
    return {"status": "cancelling"}


@router.get("/operations/{operation_id}")
def document_operation(company_id: uuid.UUID, operation_id: uuid.UUID,
                       companies: CompanySvc, current_user: CurrentUser):
    companies.get(current_user.id, company_id)
    state = operations.state(operation_id)
    return {"stage": state.stage, "progress": state.progress,
            "status": state.status, "error": state.error}


@router.get("/documents", response_model=Page[DocumentRead])
def list_documents(
    company_id: uuid.UUID,
    documents: DocumentSvc,
    current_user: CurrentUser,
    paging: Paging,
):
    items, total = documents.list(current_user.id, company_id, paging.limit, paging.offset)
    return Page[DocumentRead](
        items=[DocumentRead.model_validate(d) for d in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    documents: DocumentSvc,
    current_user: CurrentUser,
):
    return _detail(documents, documents.get(current_user.id, company_id, document_id))


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkRead])
def list_chunks(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    documents: DocumentSvc,
    current_user: CurrentUser,
):
    """The parsed structure. Useful without AI: it shows what was understood."""
    return documents.chunks(current_user.id, company_id, document_id)


@router.post(
    "/documents/{document_id}/embeddings",
    response_model=DocumentDetail,
    status_code=status.HTTP_200_OK,
)
def retry_document_embeddings(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    companies: CompanySvc,
    documents: DocumentSvc,
    ingestion: IngestionSvc,
    current_user: CurrentUser,
    settings: AppSettings,
):
    """
    Resume embedding for a document whose semantic chunks already exist.

    Does not re-upload or re-parse. Fills NULL embeddings only.
    """
    companies.get(current_user.id, company_id)
    document = documents.get(current_user.id, company_id, document_id)
    if not settings.ai_features_enabled:
        from app.core.errors import ServiceUnavailableError

        raise ServiceUnavailableError(
            "Embeddings require AI features to be enabled.",
            details={"reason": "ai_features_disabled"},
        )
    ingestion.embed_missing(company_id=company_id, document_id=document.id)
    documents.sync_company_count(company_id)
    return _detail(documents, documents.get(current_user.id, company_id, document_id))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    documents: DocumentSvc,
    current_user: CurrentUser,
) -> None:
    documents.delete(current_user.id, company_id, document_id)
    documents.sync_company_count(company_id)


@router.get("/stats", response_model=CompanyStats, tags=["dashboard"])
def company_stats(company_id: uuid.UUID, documents: DocumentSvc, current_user: CurrentUser):
    return documents.stats(current_user.id, company_id)
