"""
Shared embedding profile for remote Nomic and local SentenceTransformer.

Both paths must apply identical preprocessing and produce the same 768-d space.
Do not mix incompatible vectors in pgvector.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

TaskType = Literal["query", "document"]


@dataclass(frozen=True)
class EmbeddingProfile:
    """
    Single source of truth for embedding preprocessing.

    Existing remote OpenAI-compatible Nomic calls send raw strings with no
    client-side prefixes and store 768-d vectors. Local fallback must match
    that contract exactly so retrieval stays in one space.
    """

    model_family: str
    dimensions: int
    document_prefix: str = ""
    query_prefix: str = ""
    normalize: bool = True
    batch_size: int = 32

    def prepare(self, texts: list[str], *, task: TaskType) -> list[str]:
        prefix = self.query_prefix if task == "query" else self.document_prefix
        if not prefix:
            return list(texts)
        return [f"{prefix}{text}" for text in texts]

    def postprocess(self, vectors: list[list[float]]) -> list[list[float]]:
        if not self.normalize:
            return vectors
        return [_l2_normalize(vector) for vector in vectors]

    def validate_dimensions(self, vectors: list[list[float]]) -> None:
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimensions}, got {len(vector)}"
                )


# Match the deployed remote Nomic OpenAI-compatible path used by ingestion and
# retrieval today: 768 dims, no client prefixes, L2-normalized for cosine.
NOMIC_V15_PROFILE = EmbeddingProfile(
    model_family="nomic-embed-text-v1.5",
    dimensions=768,
    document_prefix="",
    query_prefix="",
    normalize=True,
    batch_size=32,
)

# Fixed strings for remote↔local compatibility self-test (not user content).
COMPAT_SENTINEL_QUERY = "cybrain embedding compatibility probe query"
COMPAT_SENTINEL_DOCUMENT = (
    "SOP section: Supplier qualification requires documented QA approval "
    "before first use of an external material supplier."
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return list(vector)
    return [x / norm for x in vector]
