from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.companies.router import router as companies_router
from app.modules.documents.router import router as documents_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.knowledge.retrieval_router import router as retrieval_router
from app.modules.sops.router import router as sops_router
from app.modules.ai.router import router as ai_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(documents_router)
api_router.include_router(knowledge_router)
api_router.include_router(retrieval_router)
api_router.include_router(sops_router)
api_router.include_router(ai_router)

# Generation-context preview is a development endpoint (404 in production).
# The read-only Knowledge Object endpoint is safe without inference.
