import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.companies.models import Company, CompanyOnboardingProfile, CompanyRegulation
from app.modules.auth.models import UserCompanyAccess


class CompanyRepository:
    """
    Data access for companies.

    Every read is scoped to the requesting user's accessible companies. Scoping
    lives here rather than in the routers so a handler cannot forget it and leak
    another company's data (CLAUDE.md §4).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _accessible(self, user_id: uuid.UUID):
        return (
            select(Company)
            .join(UserCompanyAccess, UserCompanyAccess.company_id == Company.id)
            .where(UserCompanyAccess.user_id == user_id)
        )

    def list_for_user(
        self,
        user_id: uuid.UUID,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Company], int]:
        """Returns one page plus the total, so a client can page correctly."""
        stmt = self._accessible(user_id)
        if search:
            stmt = stmt.where(Company.name.ilike(f"%{search}%"))

        total = self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        page = stmt.order_by(Company.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(page).unique().all()), int(total or 0)

    def get_for_user(self, user_id: uuid.UUID, company_id: uuid.UUID) -> Company | None:
        stmt = self._accessible(user_id).where(Company.id == company_id)
        return self.db.scalars(stmt).unique().one_or_none()

    def get_by_creation_request(
        self, user_id: uuid.UUID, creation_request_id: uuid.UUID
    ) -> Company | None:
        stmt = self._accessible(user_id).where(Company.creation_request_id == creation_request_id)
        return self.db.scalars(stmt).unique().one_or_none()

    def create(
        self,
        data: dict,
        regulation_ids: list[str],
        onboarding: dict | None = None,
    ) -> Company:
        company = Company(**data)
        company.regulations = [
            CompanyRegulation(regulation_id=rid, position=index)
            for index, rid in enumerate(regulation_ids)
        ]
        if onboarding is not None:
            company.onboarding_profile = CompanyOnboardingProfile(**onboarding)
        self.db.add(company)
        self.db.flush()
        return company

    def upsert_onboarding(self, company: Company, onboarding: dict) -> None:
        if company.onboarding_profile is None:
            company.onboarding_profile = CompanyOnboardingProfile(
                company_id=company.id, **onboarding
            )
        else:
            for field, value in onboarding.items():
                setattr(company.onboarding_profile, field, value)
        self.db.flush()

    def replace_regulations(self, company: Company, regulation_ids: list[str]) -> None:
        company.regulations.clear()
        self.db.flush()
        company.regulations = [
            CompanyRegulation(regulation_id=rid, position=index)
            for index, rid in enumerate(regulation_ids)
        ]
        self.db.flush()

    def grant_access(self, user_id: uuid.UUID, company_id: uuid.UUID, role: str = "owner") -> None:
        self.db.add(UserCompanyAccess(user_id=user_id, company_id=company_id, role=role))
        self.db.flush()

    def delete(self, company: Company) -> None:
        self.db.delete(company)
        self.db.flush()
