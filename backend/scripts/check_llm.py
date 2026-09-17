"""
Probe the configured local LLM endpoint and report exactly what to put in .env.

Lists the models the server advertises, then tries a chat completion and an
embedding, reporting the real embedding dimension so LLM_EMBEDDING_DIMENSIONS
is measured rather than guessed.

    python scripts/check_llm.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.integrations.llm.base import ChatMessage, LLMError  # noqa: E402
from app.integrations.llm.factory import get_llm_provider  # noqa: E402

settings = get_settings()
provider = get_llm_provider()

print(f"provider   : {provider.name}")
print(f"base_url   : {settings.llm_base_url}")
print(f"chat model : {provider.chat_model}")
print(f"embed model: {provider.embedding_model}")
print()

# ---------------------------------------------------------------- reachability
print("1. endpoint reachable ...", end=" ")
if not provider.health():
    print("NO")
    print(f"\n   Nothing is answering at {settings.llm_base_url}.")
    if provider.name == "openai_compatible":
        print("   In LM Studio: Developer tab -> select a model -> Start Server.")
        print("   Then confirm the port it prints matches LLM_BASE_URL.")
    else:
        print("   Start Ollama, or switch LLM_PROVIDER=openai_compatible.")
    sys.exit(1)
print("yes")

# --------------------------------------------------------------- model listing
print("2. models the server advertises:")
try:
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
    listing = httpx.get(f"{settings.llm_base_url.rstrip('/')}/models", headers=headers, timeout=10).json()
    ids = [m.get("id") for m in listing.get("data", []) if m.get("id")]
    for model_id in ids:
        print(f"     - {model_id}")
    if not ids:
        print("     (none reported)")
except Exception as exc:  # noqa: BLE001 - purely diagnostic
    ids = []
    print(f"     could not list models: {exc}")

# ------------------------------------------------------------------ chat check
print("3. chat completion ...", end=" ")
try:
    reply = provider.complete(
        [
            ChatMessage(role="system", content="Reply with exactly one word."),
            ChatMessage(role="user", content="Say: ready"),
        ],
        max_tokens=16,
    )
    print("ok")
    print(f"     model replied : {reply.text.strip()[:80]!r}")
    print(f"     reported model: {reply.model}")
except LLMError as exc:
    print("FAILED")
    print(f"     {exc}")
    if ids:
        print(f"     Set LLM_CHAT_MODEL to one of: {', '.join(ids)}")
    sys.exit(1)

# ------------------------------------------------------------- embedding check
print("4. embeddings ...", end=" ")
try:
    vectors = provider.embed(["Lieferantenqualifizierung", "supplier qualification"])
    dimension = len(vectors[0])
    print("ok")
    print(f"     vectors returned : {len(vectors)}")
    print(f"     ACTUAL dimension : {dimension}")
    if dimension != settings.llm_embedding_dimensions:
        print()
        print(f"     >>> LLM_EMBEDDING_DIMENSIONS is {settings.llm_embedding_dimensions}, "
              f"but this model returns {dimension}.")
        print(f"     >>> Set LLM_EMBEDDING_DIMENSIONS={dimension} in .env before embedding anything.")
        print("     >>> The value fixes the pgvector column width; changing it later")
        print("         means a migration and a full re-embed.")
        sys.exit(1)
    print("     matches LLM_EMBEDDING_DIMENSIONS: yes")
except LLMError as exc:
    print("FAILED")
    print(f"     {exc}")
    print("     LM Studio needs an embedding model loaded as well as a chat model.")
    print("     Load one (for example nomic-embed-text or bge-m3), then set")
    print("     LLM_EMBEDDING_MODEL to the id shown above.")
    sys.exit(1)

print("\nAll checks passed. The local model is wired up correctly.")
