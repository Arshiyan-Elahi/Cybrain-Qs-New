"""Real local Nomic smoke test (loads nomic-ai/nomic-embed-text-v1.5)."""

from __future__ import annotations

import math

import pytest

from app.integrations.llm.embedding_profile import NOMIC_V15_PROFILE
from app.integrations.llm.local_embeddings import LocalNomicEmbedder, clear_local_model_cache


@pytest.mark.requires_local_nomic
def test_local_nomic_embeds_one_finite_768_vector():
    clear_local_model_cache()
    embedder = LocalNomicEmbedder(
        model_id="nomic-ai/nomic-embed-text-v1.5",
        profile=NOMIC_V15_PROFILE,
    )
    vectors = embedder.embed(["test document"], task="document")
    assert len(vectors) == 1
    vector = vectors[0]
    assert len(vector) == 768
    assert all(math.isfinite(x) for x in vector)
