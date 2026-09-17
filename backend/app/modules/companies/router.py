import uuid

from fastapi import APIRouter, Query, status

from app.core.pagination import Page, Paging
from app.modules.auth.dependencies import CurrentUser
from app.modules.companies.dependencies import CompanySvc
from app.modules.companies.schemas import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=Page[CompanyRead])
def list_companies(
    service: CompanySvc,
    current_user: CurrentUser,
    paging: Paging,
    search: str | None = Query(default=None, max_length=200),
):
    items, total = service.list(current_user.id, search, paging.limit, paging.offset)
    return Page[CompanyRead](
        items=[CompanyRead.model_validate(c) for c in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, service: CompanySvc, current_user: CurrentUser):
    return service.create(current_user.id, payload)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: uuid.UUID, service: CompanySvc, current_user: CurrentUser):
    return service.get(current_user.id, company_id)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    service: CompanySvc,
    current_user: CurrentUser,
):
    return service.update(current_user.id, company_id, payload)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: uuid.UUID, service: CompanySvc, current_user: CurrentUser) -> None:
    service.delete(current_user.id, company_id)
