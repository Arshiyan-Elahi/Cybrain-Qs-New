import time
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.logging import company_id_var, get_logger, log_event, logging_flags, maybe_content
from app.shared.enums import KnowledgeTier
from app.integrations.llm.base import LLMProvider
from app.modules.documents.models import Document, DocumentChunk

logger = get_logger("app.retrieval")


@dataclass
class RetrievedChunk:
    """A hit plus everything needed to trace it back to its source."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    text: str
    tier: str
    location: str
    heading_path: list[str]
    distance: float

    @property
    def similarity(self) -> float:
        return 1.0 - self.distance


class RetrievalService:
    """
    Tier-aware retrieval over pgvector.

    Two rules are structural here, not conventions:

    1. `company_id` is applied inside the query, before the vector search. There
       is no mode that searches across companies.
    2. Every hit carries its `tier` and source location, so downstream code and
       the UI can never present industry or global content as the company's own.
    """

    def __init__(self, db: Session, llm: LLMProvider) -> None:
        self.db = db
        self.llm = llm

    def _base_query(self, company_id: uuid.UUID, tiers: list[str] | None) -> Select:
        stmt = (
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.company_id == company_id)
            .where(DocumentChunk.embedding.is_not(None))
        )
        if tiers:
            stmt = stmt.where(DocumentChunk.tier.in_(tiers))
        return stmt

    def search(
        self,
        *,
        company_id: uuid.UUID,
        query: str,
        limit: int = 5,
        tiers: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        company_id_var.set(str(company_id))
        flags = logging_flags()
        started = time.perf_counter()
        if flags.get("log_retrieval", True):
            log_event(
                logger,
                "retrieval_started",
                "Retrieval started",
                company_id=str(company_id),
                query=maybe_content(
                    query,
                    enabled=flags.get("log_ai_content", False),
                    max_chars=flags.get("log_ai_content_max_chars", 2000),
                )
                or (query[:120] + ("..." if len(query) > 120 else "")),
                mode="semantic",
                top_k=limit,
            )
        try:
            vectors = self.llm.embed([query], task="query")  # type: ignore[call-arg]
        except TypeError:
            vectors = self.llm.embed([query])
        if not vectors:
            if flags.get("log_retrieval", True):
                log_event(
                    logger,
                    "retrieval_completed",
                    "Retrieval completed with no vector",
                    company_id=str(company_id),
                    result_count=0,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    results=[],
                )
            return []
        hits = self.search_by_vector(
            company_id=company_id, vector=vectors[0], limit=limit, tiers=tiers
        )
        if flags.get("log_retrieval", True):
            results = [
                {
                    "rank": index,
                    "chunk_id": str(hit.chunk_id),
                    "document_id": str(hit.document_id),
                    "document": hit.document_filename,
                    "section": " > ".join(hit.heading_path) if hit.heading_path else hit.location,
                    "similarity_score": round(hit.similarity, 4),
                }
                for index, hit in enumerate(hits, start=1)
            ]
            log_event(
                logger,
                "retrieval_completed",
                f"Retrieval completed with {len(hits)} hits",
                company_id=str(company_id),
                result_count=len(hits),
                latency_ms=int((time.perf_counter() - started) * 1000),
                results=results,
            )
        return hits

    def search_by_vector(
        self,
        *,
        company_id: uuid.UUID,
        vector: list[float],
        limit: int = 5,
        tiers: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        distance = DocumentChunk.embedding.cosine_distance(vector)
        stmt = (
            self._base_query(company_id, tiers)
            .add_columns(distance.label("distance"))
            .order_by(distance)
            .limit(limit)
        )
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_filename=filename,
                text=chunk.text,
                tier=chunk.tier,
                location=chunk.location,
                heading_path=list(chunk.heading_path),
                distance=float(dist),
            )
            for chunk, filename, dist in self.db.execute(stmt).all()
        ]

    def build_context(self, hits: list[RetrievedChunk]) -> str:
        """
        Format hits for a prompt with the tier attached to every block.

        The label is not decoration: it is what stops the model presenting
        industry or global material as this company's verified practice.
        """
        blocks = []
        for index, hit in enumerate(hits, start=1):
            tier_label = {
                KnowledgeTier.COMPANY: "COMPANY (this client's own document)",
                KnowledgeTier.INDUSTRY: "INDUSTRY (sector norm, not this client's)",
                KnowledgeTier.GLOBAL: "GLOBAL (general baseline, not this client's)",
            }.get(hit.tier, hit.tier.upper())
            blocks.append(
                f"[{index}] tier={tier_label}\n"
                f"source={hit.document_filename} :: {hit.location}\n"
                f"{hit.text}"
            )
        return "\n\n".join(blocks)
