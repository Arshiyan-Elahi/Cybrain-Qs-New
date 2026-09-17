from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Re-export so existing `from app.integrations.llm.base import LLMError` keeps working.
from app.integrations.llm.errors import LLMError as LLMError  # noqa: F401


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class Completion:
    """
    A model response plus the attribution the domain requires.

    `model` and `provider` are recorded with anything this produces, because a
    Knowledge Object or generated SOP section must be traceable to the exact
    model that produced it (CLAUDE.md §4).
    """

    text: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """
    The only surface the rest of the application may depend on.

    Swapping local runtime or model means adding an implementation here and
    changing configuration; no service, router or migration changes.
    """

    name: str
    chat_model: str
    embedding_model: str
    embedding_dimensions: int

    def health(self) -> bool:
        """True when the endpoint is reachable and the chat model is present."""
        ...

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Completion:
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per input, in the same order."""
        ...
