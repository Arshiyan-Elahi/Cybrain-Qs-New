from typing import Annotated

from fastapi import Depends

from app.core.dependencies import DbSession
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService


def get_company_repository(db: DbSession) -> CompanyRepository:
    return CompanyRepository(db)


CompanyRepo = Annotated[CompanyRepository, Depends(get_company_repository)]


def get_company_service(db: DbSession, repo: CompanyRepo) -> CompanyService:
    return CompanyService(db, repo)


CompanySvc = Annotated[CompanyService, Depends(get_company_service)]
