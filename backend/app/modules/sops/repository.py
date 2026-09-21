import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.sops.models import SopProject


class SopProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_company(self, company_id: uuid.UUID, project_id: uuid.UUID) -> SopProject | None:
        return self.db.scalar(
            select(SopProject).where(
                SopProject.id == project_id,
                SopProject.company_id == company_id,
            )
        )

    def add(self, project: SopProject) -> SopProject:
        self.db.add(project)
        self.db.flush()
        return project
