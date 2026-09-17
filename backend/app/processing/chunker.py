"""
Structure-based chunking.

Chunks follow section boundaries rather than a fixed character count, so a
chunk never splits a table or half a procedure. Every chunk carries the heading
path it came from, which is what lets retrieval report where a fact lives.
"""

from dataclasses import dataclass, field
import hashlib

from app.processing.extractor import ExtractedBlock, ExtractedDocument

DEFAULT_MAX_CHARS = 1200


@dataclass
class Chunk:
    text: str
    order: int
    heading_path: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    section_id: str = ""
    blocks: list[dict] = field(default_factory=list)
    is_semantic: bool = True

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def location(self) -> str:
        """Human-readable source location, recorded as provenance."""
        where = " > ".join(self.heading_path) if self.heading_path else "(no section)"
        if self.page_start:
            span = (
                f"p.{self.page_start}"
                if self.page_start == self.page_end
                else f"pp.{self.page_start}-{self.page_end}"
            )
            return f"{where} [{span}]"
        return where


def _heading_path(stack: list[tuple[int, str]]) -> list[str]:
    return [title for _, title in stack]


def _flush(
    buffer: list[ExtractedBlock], stack: list[tuple[int, str]], order: int
) -> Chunk | None:
    if not buffer:
        return None
    pages = [b.page for b in buffer if b.page is not None]
    path = _heading_path(stack)
    semantic = all(block.semantic for block in buffer)
    section_key = "\n".join(path) if path else "administrative"
    return Chunk(
        text="\n".join(b.text for b in buffer).strip(),
        order=order,
        heading_path=path,
        page_start=min(pages) if pages else None,
        page_end=max(pages) if pages else None,
        section_id=hashlib.sha1(section_key.encode()).hexdigest()[:16],
        blocks=[{"type": b.kind, "text": b.text, "structured": b.structured} for b in buffer],
        is_semantic=semantic,
    )


def chunk_document(
    document: ExtractedDocument, max_chars: int = DEFAULT_MAX_CHARS
) -> list[Chunk]:
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    buffer: list[ExtractedBlock] = []
    size = 0

    def flush() -> None:
        nonlocal buffer, size
        chunk = _flush(buffer, stack, len(chunks))
        if chunk and chunk.text:
            chunks.append(chunk)
        buffer, size = [], 0

    for block in document.blocks:
        if block.kind == "heading":
            # A new section always starts a new chunk.
            flush()
            level = block.level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, block.text))
            continue

        # A table is atomic: never merged into an oversized chunk, never split.
        if block.kind in ("table", "approval_signature"):
            flush()
            buffer = [block]
            flush()
            continue

        if size and size + len(block.text) > max_chars:
            # Oversized section: split on a paragraph boundary, keeping the
            # heading path so both halves stay locatable.
            flush()

        buffer.append(block)
        size += len(block.text) + 1

    flush()
    return chunks
