from typing import Annotated

from fastapi import Depends

from app.core.dependencies import DbSession
from app.modules.companies.dependencies import CompanySvc
from app.modules.knowledge.service import KnowledgeService


def get_knowledge_service(db: DbSession, companies: CompanySvc) -> KnowledgeService:
    return KnowledgeService(db, companies)


KnowledgeSvc = Annotated[KnowledgeService, Depends(get_knowledge_service)]
