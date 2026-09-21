from typing import Annotated

from fastapi import Depends

from app.core.dependencies import DbSession, get_llm_provider_dep
from app.modules.companies.dependencies import CompanySvc
from app.modules.knowledge.dependencies import GenerationContextSvc
from app.modules.sops.repository import SopProjectRepository
from app.modules.sops.service import SopProjectService


def get_sop_project_repository(db: DbSession) -> SopProjectRepository:
    return SopProjectRepository(db)


def get_sop_project_service(
    db: DbSession,
    companies: CompanySvc,
    context: GenerationContextSvc,
    llm=Depends(get_llm_provider_dep),
) -> SopProjectService:
    return SopProjectService(db, companies, SopProjectRepository(db), context, llm)


SopProjectSvc = Annotated[SopProjectService, Depends(get_sop_project_service)]
