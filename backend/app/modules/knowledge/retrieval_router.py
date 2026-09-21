"""Development preview of the SOP generation context package."""

import uuid

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.dependencies import require_ai_ready
from app.core.errors import NotFoundError
from app.modules.auth.dependencies import CurrentUser
from app.modules.knowledge.dependencies import GenerationContextSvc
from app.modules.knowledge.generation_context import GenerationContextPackage
from app.modules.knowledge.schemas import (
    CompanyProfileContextRead,
    GenerationContextRead,
    KnowledgeCitationRead,
    KnowledgeGroupRead,
    OnboardingContextRead,
    RegulatoryProfileRead,
    RetrievalMetadataRead,
    RetrievalPreviewRequest,
    RetrievedChunkRead,
    RetrievedKnowledgeRead,
)

router = APIRouter(prefix="/companies/{company_id}/retrieval", tags=["retrieval"])


@router.post(
    "/preview",
    response_model=GenerationContextRead,
    dependencies=[Depends(require_ai_ready)],
)
def preview_generation_context(
    company_id: uuid.UUID,
    payload: RetrievalPreviewRequest,
    service: GenerationContextSvc,
    current_user: CurrentUser,
):
    settings = get_settings()
    if settings.is_production:
        raise NotFoundError("Not found.")
    package = service.build(
        current_user.id,
        company_id,
        payload.query,
        knowledge_limit=payload.knowledge_limit,
        chunk_limit=payload.chunk_limit,
    )
    return _to_read(package)


def _to_read(package: GenerationContextPackage) -> GenerationContextRead:
    onboarding = None
    if package.onboarding is not None:
        onboarding = OnboardingContextRead(
            tone_id=package.onboarding.tone_id,
            formality_id=package.onboarding.formality_id,
            person_id=package.onboarding.person_id,
            prefer_existing_terms=package.onboarding.prefer_existing_terms,
            require_human_verification=package.onboarding.require_human_verification,
        )
    return GenerationContextRead(
        query=package.query,
        company=CompanyProfileContextRead(
            id=package.company.id,
            name=package.company.name,
            industry_key=package.company.industry_key,
            location_key=package.company.location_key,
            primary_language_key=package.company.primary_language_key,
        ),
        regulatory_profile=RegulatoryProfileRead(
            regulation_ids=package.regulatory_profile.regulation_ids
        ),
        onboarding=onboarding,
        knowledge=[
            KnowledgeGroupRead(
                type=kind,
                items=[
                    RetrievedKnowledgeRead(
                        id=item.id,
                        type=item.type,
                        label=item.label,
                        payload=item.payload,
                        tier=item.tier,
                        version=item.version,
                        status=item.status,
                        similarity=item.similarity,
                        citation=KnowledgeCitationRead(
                            source_kind=item.citation.source_kind,
                            source_document_id=item.citation.source_document_id,
                            source_document_name=item.citation.source_document_name,
                            source_chunk_id=item.citation.source_chunk_id,
                            source_location=item.citation.source_location,
                            evidence=item.citation.evidence,
                            extraction_method=item.citation.extraction_method,
                            model_name=item.citation.model_name,
                            model_provider=item.citation.model_provider,
                            verified_by=item.citation.verified_by,
                            verified_at=item.citation.verified_at,
                        ),
                    )
                    for item in items
                ],
            )
            for kind, items in package.knowledge
        ],
        source_chunks=[
            RetrievedChunkRead(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_filename=hit.document_filename,
                text=hit.text,
                tier=hit.tier,
                location=hit.location,
                heading_path=hit.heading_path,
                similarity=round(hit.similarity, 4),
            )
            for hit in package.source_chunks
        ],
        metadata=RetrievalMetadataRead(
            query=package.metadata.query,
            mode=package.metadata.mode,
            knowledge_ranker=package.metadata.knowledge_ranker,
            embedding_model=package.metadata.embedding_model,
            embedding_dimensions=package.metadata.embedding_dimensions,
            verified_pool_size=package.metadata.verified_pool_size,
            knowledge_returned=package.metadata.knowledge_returned,
            chunk_returned=package.metadata.chunk_returned,
            latency_ms=package.metadata.latency_ms,
        ),
        notes=package.notes,
    )
