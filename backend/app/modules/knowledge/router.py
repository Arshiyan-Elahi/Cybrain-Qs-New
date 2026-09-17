import uuid

from fastapi import APIRouter, Depends

from app.core.pagination import Page, Paging
from app.modules.auth.dependencies import CurrentUser
from app.modules.knowledge.dependencies import KnowledgeSvc
from app.modules.knowledge.schemas import KnowledgeExtractionResult, KnowledgeObjectRead, KnowledgeObjectUpdate
from app.core.dependencies import require_ai_ready
from app.integrations.llm.errors import LLMError, to_ai_service_unavailable
from app.integrations.llm.factory import get_llm_provider
from app.modules.documents.cancellation import OperationCancelled, operations

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
        created, skipped = service.extract_from_chunks(current_user.id, company_id, get_llm_provider(), token)
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


@router.post("/operations/{operation_id}/cancel", status_code=202)
def cancel_knowledge_extraction(company_id: uuid.UUID, operation_id: uuid.UUID,
                                service: KnowledgeSvc, current_user: CurrentUser):
    service.companies.get(current_user.id, company_id)
    operations.cancel(operation_id)
    return {"status": "cancelling"}


@router.get("", response_model=Page[KnowledgeObjectRead])
def list_knowledge_objects(
    company_id: uuid.UUID,
    service: KnowledgeSvc,
    current_user: CurrentUser,
    paging: Paging,
):
    items, total = service.list(current_user.id, company_id, paging.limit, paging.offset)
    return Page[KnowledgeObjectRead](
        items=[KnowledgeObjectRead.model_validate(item) for item in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.patch("/{object_id}", response_model=KnowledgeObjectRead)
def edit_knowledge_object(company_id: uuid.UUID, object_id: uuid.UUID, payload: KnowledgeObjectUpdate,
                          service: KnowledgeSvc, current_user: CurrentUser):
    return service.edit(current_user.id, company_id, object_id, payload.label)


@router.post("/{object_id}/confirm", response_model=KnowledgeObjectRead)
def confirm_knowledge_object(company_id: uuid.UUID, object_id: uuid.UUID,
                             service: KnowledgeSvc, current_user: CurrentUser):
    return service.confirm(current_user.id, company_id, object_id)


@router.post("/{object_id}/reject", response_model=KnowledgeObjectRead)
def reject_knowledge_object(company_id: uuid.UUID, object_id: uuid.UUID,
                            service: KnowledgeSvc, current_user: CurrentUser):
    return service.reject(current_user.id, company_id, object_id)
