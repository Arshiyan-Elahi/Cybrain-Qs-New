"""Assemble a generation context package from verified CKM + document chunks.

This is the retrieval/context layer for later SOP blueprint/generation.
It does not draft SOP text. Trusted knowledge is verified and current only.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.logging import company_id_var, get_logger, log_event
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.embedding_profile import cosine_similarity
from app.modules.companies.models import Company
from app.modules.companies.service import CompanyService
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.models import KnowledgeObject
from app.modules.knowledge.retrieval import RetrievedChunk, RetrievalService
from app.shared.enums import KnowledgeStatus

logger = get_logger("app.retrieval.context")

DEFAULT_KNOWLEDGE_LIMIT = 20
DEFAULT_CHUNK_LIMIT = 8
MIN_KNOWLEDGE_SIMILARITY = 0.30

KNOWLEDGE_TYPE_ORDER = (
    "terminology",
    "role",
    "responsibility",
    "workflow",
    "process",
    "business_rule",
    "regulation",
    "form_or_record",
    "relationship",
    "best_practice",
    "document_structure",
    "writing_style",
    "ai_preference",
)


class ChunkSearcher(Protocol):
    """Document-chunk retrieval. RetrievalService satisfies this today."""

    def search(
        self,
        *,
        company_id: uuid.UUID,
        query: str,
        limit: int = 5,
        tiers: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        ...


class KnowledgeRanker(Protocol):
    """Rank already-trusted Knowledge Objects for a query. Swap later without changing callers."""

    def rank(
        self,
        query: str,
        items: list[KnowledgeObject],
        *,
        limit: int,
        min_similarity: float,
    ) -> list[tuple[KnowledgeObject, float]]:
        ...


@dataclass(frozen=True)
class CompanyProfileContext:
    id: uuid.UUID
    name: str
    industry_key: str
    location_key: str
    primary_language_key: str


@dataclass(frozen=True)
class RegulatoryProfile:
    regulation_ids: list[str]


@dataclass(frozen=True)
class OnboardingContext:
    tone_id: str
    formality_id: str
    person_id: str
    prefer_existing_terms: bool
    require_human_verification: bool


@dataclass(frozen=True)
class KnowledgeCitation:
    source_kind: str
    source_document_id: uuid.UUID | None
    source_document_name: str
    source_chunk_id: uuid.UUID | None
    source_location: str
    evidence: list[Any]
    extraction_method: str
    model_name: str | None
    model_provider: str | None
    verified_by: uuid.UUID | None
    verified_at: str | None


@dataclass(frozen=True)
class RetrievedKnowledge:
    id: uuid.UUID
    type: str
    label: str
    payload: dict
    tier: str
    version: int
    status: str
    similarity: float
    citation: KnowledgeCitation


@dataclass(frozen=True)
class RetrievalMetadata:
    query: str
    mode: str
    knowledge_ranker: str
    embedding_model: str
    embedding_dimensions: int
    verified_pool_size: int
    knowledge_returned: int
    chunk_returned: int
    latency_ms: int


@dataclass
class GenerationContextPackage:
    query: str
    company: CompanyProfileContext
    regulatory_profile: RegulatoryProfile
    onboarding: OnboardingContext | None
    knowledge: list[tuple[str, list[RetrievedKnowledge]]]
    source_chunks: list[RetrievedChunk]
    metadata: RetrievalMetadata
    notes: list[str] = field(default_factory=list)


class EmbeddingKnowledgeRanker:
    """Query embedding vs on-the-fly KO text embeddings. No stored KO vectors."""

    name = "query_embedding_cosine"

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def rank(
        self,
        query: str,
        items: list[KnowledgeObject],
        *,
        limit: int,
        min_similarity: float,
    ) -> list[tuple[KnowledgeObject, float]]:
        if not items:
            return []
        texts = [_ko_search_text(item) for item in items]
        query_vector = _embed_one(self.llm, query, task="query")
        item_vectors = _embed_many(self.llm, texts, task="document")
        if query_vector is None or not item_vectors:
            return _lexical_rank(query, items, limit=limit, min_similarity=min_similarity)
        scored: list[tuple[KnowledgeObject, float]] = []
        for item, vector in zip(items, item_vectors, strict=True):
            if not vector:
                continue
            score = cosine_similarity(query_vector, vector)
            if score >= min_similarity:
                scored.append((item, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]


class GenerationContextService:
    """Company-isolated context package for later SOP generation."""

    def __init__(
        self,
        db: Session,
        companies: CompanyService,
        chunks: ChunkSearcher,
        ranker: KnowledgeRanker,
        *,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None:
        self.db = db
        self.companies = companies
        self.chunks = chunks
        self.ranker = ranker
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions

    def build(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        query: str,
        *,
        knowledge_limit: int = DEFAULT_KNOWLEDGE_LIMIT,
        chunk_limit: int = DEFAULT_CHUNK_LIMIT,
    ) -> GenerationContextPackage:
        started = time.perf_counter()
        company_id = company_id if isinstance(company_id, uuid.UUID) else uuid.UUID(str(company_id))
        company = self.companies.get(user_id, company_id)
        company_id_var.set(str(company.id))
        trusted = self.trusted_knowledge(user_id, company.id)
        ranked = self.ranker.rank(
            query,
            trusted,
            limit=knowledge_limit,
            min_similarity=MIN_KNOWLEDGE_SIMILARITY,
        )
        names = self._document_names(company.id, [item for item, _score in ranked])
        retrieved = [
            _to_retrieved_knowledge(item, score, names.get(item.source_document_id, _fallback_name(item)))
            for item, score in ranked
        ]
        grouped = _group_by_type(retrieved)
        hits = self.chunks.search(company_id=company.id, query=query, limit=chunk_limit)
        hits = [hit for hit in hits if self._chunk_belongs(company.id, hit)]
        notes: list[str] = []
        if not trusted:
            notes.append(
                "No verified current Knowledge Objects exist for this company. "
                "Proposed, rejected and superseded objects are excluded from trusted CKM retrieval."
            )
        package = GenerationContextPackage(
            query=query,
            company=CompanyProfileContext(
                id=company.id,
                name=company.name,
                industry_key=company.industry_key,
                location_key=company.location_key,
                primary_language_key=company.primary_language_key,
            ),
            regulatory_profile=RegulatoryProfile(regulation_ids=list(company.regulation_ids)),
            onboarding=_onboarding_context(company),
            knowledge=grouped,
            source_chunks=hits,
            metadata=RetrievalMetadata(
                query=query,
                mode="semantic",
                knowledge_ranker=getattr(self.ranker, "name", type(self.ranker).__name__),
                embedding_model=self.embedding_model,
                embedding_dimensions=self.embedding_dimensions,
                verified_pool_size=len(trusted),
                knowledge_returned=len(retrieved),
                chunk_returned=len(hits),
                latency_ms=int((time.perf_counter() - started) * 1000),
            ),
            notes=notes,
        )
        log_event(
            logger,
            "generation_context_built",
            "Generation context assembled",
            company_id=str(company.id),
            verified_pool_size=len(trusted),
            knowledge_returned=len(retrieved),
            chunk_returned=len(hits),
            knowledge_ranker=package.metadata.knowledge_ranker,
        )
        return package

    def trusted_knowledge(self, user_id: uuid.UUID, company_id: uuid.UUID) -> list[KnowledgeObject]:
        company = self.companies.get(user_id, company_id)
        return self._trusted_knowledge(company.id)

    def _trusted_knowledge(self, company_id: uuid.UUID) -> list[KnowledgeObject]:
        # autoflush is off; pick up same-session writes (tests and preview).
        self.db.flush()
        stmt = (
            select(KnowledgeObject)
            .outerjoin(Document, Document.id == KnowledgeObject.source_document_id)
            .outerjoin(DocumentChunk, DocumentChunk.id == KnowledgeObject.source_chunk_id)
            .where(KnowledgeObject.company_id == company_id)
            .where(KnowledgeObject.status == KnowledgeStatus.VERIFIED.value)
            .where(
                or_(
                    KnowledgeObject.source_document_id.is_(None),
                    and_(Document.id.is_not(None), Document.company_id == company_id),
                )
            )
            .where(
                or_(
                    KnowledgeObject.source_chunk_id.is_(None),
                    and_(
                        DocumentChunk.id.is_not(None),
                        DocumentChunk.company_id == company_id,
                    ),
                )
            )
        )
        return list(self.db.scalars(stmt).unique().all())

    def _document_names(
        self, company_id: uuid.UUID, items: list[KnowledgeObject]
    ) -> dict[uuid.UUID, str]:
        ids = {item.source_document_id for item in items if item.source_document_id}
        if not ids:
            return {}
        return dict(
            self.db.execute(
                select(Document.id, Document.filename).where(
                    Document.company_id == company_id,
                    Document.id.in_(ids),
                )
            )
            .tuples()
            .all()
        )

    def _chunk_belongs(self, company_id: uuid.UUID, hit: RetrievedChunk) -> bool:
        owned = self.db.scalar(
            select(DocumentChunk.id).where(
                DocumentChunk.id == hit.chunk_id,
                DocumentChunk.company_id == company_id,
                DocumentChunk.document_id == hit.document_id,
            )
        )
        return owned is not None


def build_generation_context_service(
    db: Session,
    companies: CompanyService,
    llm: LLMProvider,
) -> GenerationContextService:
    return GenerationContextService(
        db,
        companies,
        RetrievalService(db, llm),
        EmbeddingKnowledgeRanker(llm),
        embedding_model=getattr(llm, "embedding_model", "") or "",
        embedding_dimensions=int(getattr(llm, "embedding_dimensions", 768) or 768),
    )


def _ko_search_text(item: KnowledgeObject) -> str:
    parts = [item.type.replace("_", " "), item.label, item.source_location]
    payload = item.payload if isinstance(item.payload, dict) else {}
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        for row in evidence:
            if isinstance(row, dict) and isinstance(row.get("snippet"), str):
                parts.append(row["snippet"][:400])
    return " ".join(part for part in parts if part)


def _embed_one(llm: LLMProvider, text: str, *, task: str) -> list[float] | None:
    vectors = _embed_many(llm, [text], task=task)
    return vectors[0] if vectors else None


def _embed_many(llm: LLMProvider, texts: list[str], *, task: str) -> list[list[float]]:
    if not texts:
        return []
    try:
        return llm.embed(texts, task=task)  # type: ignore[call-arg]
    except TypeError:
        return llm.embed(texts)


def _lexical_rank(
    query: str,
    items: list[KnowledgeObject],
    *,
    limit: int,
    min_similarity: float,
) -> list[tuple[KnowledgeObject, float]]:
    terms = {token for token in query.casefold().split() if len(token) > 2}
    if not terms:
        return []
    scored: list[tuple[KnowledgeObject, float]] = []
    for item in items:
        haystack = _ko_search_text(item).casefold()
        hits = sum(1 for term in terms if term in haystack)
        score = hits / len(terms)
        if score >= min_similarity:
            scored.append((item, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]


def _group_by_type(items: list[RetrievedKnowledge]) -> list[tuple[str, list[RetrievedKnowledge]]]:
    buckets: dict[str, list[RetrievedKnowledge]] = defaultdict(list)
    for item in items:
        buckets[item.type].append(item)
    ordered: list[tuple[str, list[RetrievedKnowledge]]] = []
    seen: set[str] = set()
    for kind in KNOWLEDGE_TYPE_ORDER:
        if kind in buckets:
            ordered.append((kind, buckets[kind]))
            seen.add(kind)
    for kind, group in buckets.items():
        if kind not in seen:
            ordered.append((kind, group))
    return ordered


def _onboarding_context(company: Company) -> OnboardingContext | None:
    profile = company.onboarding_profile
    if profile is None:
        return None
    return OnboardingContext(
        tone_id=profile.tone_id,
        formality_id=profile.formality_id,
        person_id=profile.person_id,
        prefer_existing_terms=bool(profile.prefer_existing_terms),
        require_human_verification=bool(profile.require_human_verification),
    )


def _fallback_name(item: KnowledgeObject) -> str:
    if item.source_kind == "onboarding":
        return "Company onboarding"
    if item.source_document_id is None:
        return "Human entry"
    return "Source document"


def _to_retrieved_knowledge(
    item: KnowledgeObject, score: float, document_name: str
) -> RetrievedKnowledge:
    payload = dict(item.payload) if isinstance(item.payload, dict) else {}
    evidence = payload.get("evidence")
    return RetrievedKnowledge(
        id=item.id,
        type=str(item.type),
        label=item.label,
        payload=payload,
        tier=str(item.tier),
        version=item.version,
        status=str(item.status),
        similarity=round(float(score), 4),
        citation=KnowledgeCitation(
            source_kind=item.source_kind,
            source_document_id=item.source_document_id,
            source_document_name=document_name,
            source_chunk_id=item.source_chunk_id,
            source_location=item.source_location,
            evidence=list(evidence) if isinstance(evidence, list) else [],
            extraction_method=item.extraction_method,
            model_name=item.model_name,
            model_provider=item.model_provider,
            verified_by=item.verified_by,
            verified_at=item.verified_at.isoformat() if item.verified_at else None,
        ),
    )
