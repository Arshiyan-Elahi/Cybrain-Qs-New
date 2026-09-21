"""Real local Nomic smoke: embed ['test document'] → one finite 768-d vector."""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.llm.embedding_profile import NOMIC_V15_PROFILE
from app.integrations.llm.local_embeddings import LocalNomicEmbedder, clear_local_model_cache


def main() -> int:
    clear_local_model_cache()
    embedder = LocalNomicEmbedder(
        model_id="nomic-ai/nomic-embed-text-v1.5",
        profile=NOMIC_V15_PROFILE,
    )
    vectors = embedder.embed(["test document"], task="document")
    if len(vectors) != 1:
        print(f"FAIL: expected 1 vector, got {len(vectors)}")
        return 1
    vector = vectors[0]
    if len(vector) != 768:
        print(f"FAIL: expected 768 dimensions, got {len(vector)}")
        return 1
    if not all(math.isfinite(x) for x in vector):
        print("FAIL: vector contains non-finite values")
        return 1
    print(
        "PASS: 1 finite 768-d vector "
        f"model={embedder.embedding_model} dims={embedder.embedding_dimensions}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
