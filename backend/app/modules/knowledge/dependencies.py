from typing import Annotated

from fastapi import Depends

from app.core.dependencies import DbSession, get_llm_provider_dep
from app.modules.companies.dependencies import CompanySvc
from app.modules.knowledge.generation_context import (
    GenerationContextService,
    build_generation_context_service,
)
from app.modules.knowledge.service import KnowledgeService


def get_knowledge_service(db: DbSession, companies: CompanySvc) -> KnowledgeService:
    return KnowledgeService(db, companies)


def get_generation_context_service(
    db: DbSession, companies: CompanySvc, llm=Depends(get_llm_provider_dep)
) -> GenerationContextService:
    return build_generation_context_service(db, companies, llm)


KnowledgeSvc = Annotated[KnowledgeService, Depends(get_knowledge_service)]
GenerationContextSvc = Annotated[
    GenerationContextService, Depends(get_generation_context_service)
]
