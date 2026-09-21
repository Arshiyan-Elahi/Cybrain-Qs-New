"""
Single import point that makes every mapped class visible.

SQLAlchemy resolves string-based relationships only once all mappers are
imported. Importing them here — rather than each model importing its
neighbour at the bottom of the file — removes the circular-import workarounds
and gives Alembic a complete metadata graph.
"""

from app.shared.models import Base

# Import order is irrelevant; presence is what matters.
from app.modules.auth.models import User, UserCompanyAccess  # noqa: F401
from app.modules.companies.models import (  # noqa: F401
    Company,
    CompanyOnboardingProfile,
    CompanyRegulation,
)
from app.modules.documents.models import Document, DocumentChunk  # noqa: F401
from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory  # noqa: F401
from app.modules.sops.models import SopProject  # noqa: F401

__all__ = [
    "Base",
    "Company",
    "CompanyOnboardingProfile",
    "CompanyRegulation",
    "Document",
    "DocumentChunk",
    "KnowledgeObject",
    "KnowledgeObjectHistory",
    "SopProject",
    "User",
    "UserCompanyAccess",
]
