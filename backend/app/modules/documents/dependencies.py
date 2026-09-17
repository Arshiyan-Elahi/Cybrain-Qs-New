from typing import Annotated

from fastapi import Depends

from app.core.dependencies import AppSettings, DbSession
from app.modules.companies.dependencies import CompanySvc
from app.modules.documents.ingestion import IngestionService
from app.modules.documents.service import DocumentService


def get_document_service(db: DbSession, companies: CompanySvc) -> DocumentService:
    return DocumentService(db, companies)


DocumentSvc = Annotated[DocumentService, Depends(get_document_service)]


def get_ingestion_service(db: DbSession, settings: AppSettings) -> IngestionService:
    """
    Build the core parse/chunk path without an LLM unless AI is enabled.

    Provider construction is lazy so normal document ingestion has no inference
    dependency, while AI-enabled ingestion can create embeddings.
    """
    if not settings.ai_features_enabled:
        return IngestionService(db)

    from app.integrations.llm.factory import get_llm_provider

    return IngestionService(db, get_llm_provider())


IngestionSvc = Annotated[IngestionService, Depends(get_ingestion_service)]
