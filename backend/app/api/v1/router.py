from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.companies.router import router as companies_router
from app.modules.documents.router import router as documents_router
from app.modules.knowledge.router import router as knowledge_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(documents_router)
api_router.include_router(knowledge_router)

# Retrieval remains unregistered while AI is off. The read-only Knowledge
# Object endpoint is safe without inference and exposes only persisted rows.
