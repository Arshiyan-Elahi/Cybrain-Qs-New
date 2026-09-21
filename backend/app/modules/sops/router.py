import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import require_ai_ready
from app.modules.auth.dependencies import CurrentUser
from app.modules.sops.dependencies import SopProjectSvc
from app.modules.sops.schemas import SopProjectCreate, SopProjectRead

router = APIRouter(prefix="/companies/{company_id}/sop-projects", tags=["sops"])


@router.post("", response_model=SopProjectRead, status_code=status.HTTP_201_CREATED)
def create_sop_project(
    company_id: uuid.UUID,
    payload: SopProjectCreate,
    service: SopProjectSvc,
    current_user: CurrentUser,
):
    return service.create(current_user.id, company_id, payload)


@router.get("/{project_id}", response_model=SopProjectRead)
def get_sop_project(
    company_id: uuid.UUID,
    project_id: uuid.UUID,
    service: SopProjectSvc,
    current_user: CurrentUser,
):
    return service.get(current_user.id, company_id, project_id)


@router.post(
    "/{project_id}/blueprint",
    response_model=SopProjectRead,
    dependencies=[Depends(require_ai_ready)],
)
def build_sop_blueprint(
    company_id: uuid.UUID,
    project_id: uuid.UUID,
    service: SopProjectSvc,
    current_user: CurrentUser,
):
    return service.build_blueprint(current_user.id, company_id, project_id)


@router.post("/{project_id}/ready", response_model=SopProjectRead)
def mark_sop_generation_ready(
    company_id: uuid.UUID,
    project_id: uuid.UUID,
    service: SopProjectSvc,
    current_user: CurrentUser,
):
    return service.mark_generation_ready(current_user.id, company_id, project_id)
