import uuid

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_ai_ready
from app.core.pagination import Page, Paging
from app.integrations.llm.errors import LLMError, to_ai_service_unavailable
from app.integrations.llm.factory import get_llm_provider
from app.modules.auth.dependencies import CurrentUser
from app.modules.documents.cancellation import OperationCancelled, operations
from app.modules.knowledge.dependencies import KnowledgeSvc
from app.modules.knowledge.schemas import (
    KnowledgeExtractionResult,
    KnowledgeHistoryRead,
    KnowledgeObjectRead,
    KnowledgeObjectUpdate,
    KnowledgeOnboardingResult,
)

router = APIRouter(prefix="/companies/{company_id}/knowledge-objects", tags=["knowledge"])


@router.post("/extract", response_model=KnowledgeExtractionResult, dependencies=[Depends(require_ai_ready)])
def extract_knowledge_objects(
    company_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
    operation_id: uuid.UUID | None = None,
):
    token = operations.token(operation_id) if operation_id else None
    try:
        created, skipped = service.extract_from_chunks(
            current_user.id, company_id, get_llm_provider(), token
        )
        return KnowledgeExtractionResult(created=created, skipped_chunks=skipped)
    except LLMError as exc:
        service.db.rollback()
        raise to_ai_service_unavailable(exc) from exc
    except OperationCancelled:
        service.db.rollback()
        return KnowledgeExtractionResult(created=0, skipped_chunks=0, status="cancelled")
    finally:
        if operation_id:
            operations.finish(operation_id)


@router.post("/from-onboarding", response_model=KnowledgeOnboardingResult)
def propose_from_onboarding(
    company_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
):
    created = service.propose_from_onboarding(current_user.id, company_id)
    return KnowledgeOnboardingResult(created=created)


@router.post("/operations/{operation_id}/cancel", status_code=202)
def cancel_knowledge_extraction(
    company_id: uuid.UUID,
    operation_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
):
    service.companies.get(current_user.id, company_id)
    operations.cancel(operation_id)
    return {"status": "cancelling"}


@router.get("", response_model=Page[KnowledgeObjectRead])
def list_knowledge_objects(
    company_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
    paging: Paging,
    type: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, max_length=16),
    source_kind: str | None = Query(default=None, max_length=32),
    source_document_id: uuid.UUID | None = Query(default=None),
    origin: str | None = Query(default=None, pattern="^(onboarding|document)$"),
    include_superseded: bool = Query(default=False),
):
    items, total = service.list(
        current_user.id,
        company_id,
        paging.limit,
        paging.offset,
        type=type,
        status=status,
        source_kind=source_kind,
        source_document_id=source_document_id,
        origin=origin,
        include_superseded=include_superseded,
    )
    return Page[KnowledgeObjectRead](
        items=[KnowledgeObjectRead.model_validate(item) for item in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.get("/{object_id}/history", response_model=list[KnowledgeHistoryRead])
def knowledge_object_history(
    company_id: uuid.UUID,
    object_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
):
    rows = service.history(current_user.id, company_id, object_id)
    return [KnowledgeHistoryRead.model_validate(row) for row in rows]


@router.patch("/{object_id}", response_model=KnowledgeObjectRead)
def edit_knowledge_object(
    company_id: uuid.UUID,
    object_id: uuid.UUID,
    payload: KnowledgeObjectUpdate,
    service: KnowledgeSvc,
    current_user: CurrentUser,
):
    return service.edit(current_user.id, company_id, object_id, payload.label)


@router.post("/{object_id}/confirm", response_model=KnowledgeObjectRead)
def confirm_knowledge_object(
    company_id: uuid.UUID,
    object_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
):
    return service.confirm(current_user.id, company_id, object_id)


@router.post("/{object_id}/reject", response_model=KnowledgeObjectRead)
def reject_knowledge_object(
    company_id: uuid.UUID,
    object_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
):
    return service.reject(current_user.id, company_id, object_id)
