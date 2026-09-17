import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.companies.models import Company
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.schemas import CompanyCreate, CompanyUpdate


class CompanyService:
    def __init__(self, db: Session, repo: CompanyRepository) -> None:
        self.db = db
        self.repo = repo

    def list(
        self,
        user_id: uuid.UUID,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Company], int]:
        return self.repo.list_for_user(user_id, search, limit, offset)

    def get(self, user_id: uuid.UUID, company_id: uuid.UUID) -> Company:
        company = self.repo.get_for_user(user_id, company_id)
        if company is None:
            # Same response whether it does not exist or the user cannot see it,
            # so the endpoint cannot confirm another tenant's company exists.
            raise NotFoundError("Company not found.")
        return company

    def create(self, user_id: uuid.UUID, payload: CompanyCreate) -> Company:
        if payload.creation_request_id is not None:
            existing = self.repo.get_by_creation_request(user_id, payload.creation_request_id)
            if existing is not None:
                return existing

        data = payload.model_dump(exclude={"regulation_ids", "onboarding"})
        onboarding = (
            payload.onboarding.model_dump() if payload.onboarding is not None else None
        )
        try:
            with self.db.begin_nested():
                company = self.repo.create(data, payload.regulation_ids, onboarding)
                # The creator always gets access, otherwise they could not read it back.
                self.repo.grant_access(user_id, company.id, role="owner")
                self.db.flush()
            return company
        except IntegrityError:
            if payload.creation_request_id is None:
                raise
            existing = self.repo.get_by_creation_request(user_id, payload.creation_request_id)
            if existing is None:
                raise
            return existing

    def update(self, user_id: uuid.UUID, company_id: uuid.UUID, payload: CompanyUpdate) -> Company:
        company = self.get(user_id, company_id)
        changes = payload.model_dump(
            exclude_unset=True, exclude={"regulation_ids", "onboarding"}
        )
        for field, value in changes.items():
            setattr(company, field, value)
        if payload.regulation_ids is not None:
            self.repo.replace_regulations(company, payload.regulation_ids)
        if "onboarding" in payload.model_fields_set and payload.onboarding is not None:
            self.repo.upsert_onboarding(company, payload.onboarding.model_dump())
        self.db.flush()
        return company

    def delete(self, user_id: uuid.UUID, company_id: uuid.UUID) -> None:
        company = self.get(user_id, company_id)
        self.repo.delete(company)
        self.db.flush()
