"""
Turn an uploaded PDF or DOCX into ordered, structure-aware blocks.

SOPs are highly structured documents: numbered sections, responsibility tables,
step lists, referenced forms. Flattening one into a text blob throws away
exactly the signal the CKM needs, so structure is preserved here rather than
recovered later.
"""

import io
import re
from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal[
    "heading", "paragraph", "list", "table", "document_metadata",
    "approval_signature", "appendix_revision",
]

# "1.", "1.2", "4.3.1 " — the numbering SOPs almost always use for sections.
_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_LIST_ITEM = re.compile(r"^\s*(?:[-•*•]|\(?[a-z0-9]{1,3}[.)])\s+\S")


@dataclass
class ExtractedBlock:
    kind: BlockKind
    text: str
    order: int
    level: int | None = None
    page: int | None = None
    structured: dict = field(default_factory=dict)
    semantic: bool = True


@dataclass
class ExtractedDocument:
    blocks: list[ExtractedBlock]
    page_count: int
    source_format: str
    warnings: list[str] = field(default_factory=list)
    is_probably_scanned: bool = False

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks)


class UnsupportedDocumentError(ValueError):
    pass


def extract(content: bytes, filename: str) -> ExtractedDocument:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return _extract_pdf(content)
    if lowered.endswith(".docx"):
        return _extract_docx(content)
    raise UnsupportedDocumentError(
        f"Unsupported file type for {filename!r}. Supported: .pdf, .docx"
    )


# --------------------------------------------------------------------------- PDF


def _classify_line(line: str) -> tuple[BlockKind, int | None]:
    stripped = line.strip()

    match = _NUMBERED_HEADING.match(stripped)
    if match and len(stripped) <= 120:
        return "heading", match.group(1).count(".") + 1

    if _LIST_ITEM.match(line):
        return "list", None

    # Short, title-cased or upper-case lines with no terminal punctuation read
    # as headings in practice.
    if 0 < len(stripped) <= 80 and not stripped.endswith((".", ":", ";", ",")):
        letters = [c for c in stripped if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:
            return "heading", 1

    return "paragraph", None


def _extract_pdf(content: bytes) -> ExtractedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
    except (PdfReadError, OSError, ValueError) as exc:
        raise UnsupportedDocumentError(f"Could not read PDF: {exc}") from exc

    blocks: list[ExtractedBlock] = []
    warnings: list[str] = []
    empty_pages = 0
    order = 0

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - a bad page must not lose the rest
            warnings.append(f"Page {page_number} could not be parsed: {exc}")
            raw = ""

        if not raw.strip():
            empty_pages += 1
            warnings.append(f"Page {page_number} has no extractable text (likely scanned).")
            continue

        for line in raw.splitlines():
            if not line.strip():
                continue
            kind, level = _classify_line(line)
            blocks.append(
                ExtractedBlock(
                    kind=kind, text=line.strip(), order=order, level=level, page=page_number
                )
            )
            order += 1

    page_count = len(reader.pages)
    # A document that is mostly image pages needs OCR, and must be visibly
    # partial rather than silently thin.
    scanned = page_count > 0 and empty_pages / page_count >= 0.5
    if scanned:
        warnings.append(
            "Most pages contain no text layer. This document needs OCR before it can be analysed."
        )

    return ExtractedDocument(
        blocks=blocks,
        page_count=page_count,
        source_format="pdf",
        warnings=warnings,
        is_probably_scanned=scanned,
    )


# -------------------------------------------------------------------------- DOCX


def _extract_docx(content: bytes) -> ExtractedDocument:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 - python-docx raises several types
        raise UnsupportedDocumentError(f"Could not read DOCX: {exc}") from exc

    blocks: list[ExtractedBlock] = []
    order = 0

    # Walk the body in document order so tables stay between the right paragraphs.
    body = document.element.body
    seen_heading = False
    appendix_active = False
    special_content = False
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]

        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name or "").lower()
            heading_match = re.match(r"heading\s*(\d+)", style)
            appendix_match = re.match(r"appendix\s+([ivxlcdm]+)\b", text, re.I)
            custom_heading = any(word in style for word in ("appendix", "heading", "überschrift"))
            if heading_match or appendix_match or custom_heading:
                level = int(heading_match.group(1)) if heading_match else (1 if appendix_match else 2)
                blocks.append(
                    ExtractedBlock(kind="heading", text=text, order=order, level=level,
                                   structured={"style": paragraph.style.name})
                )
                seen_heading = True
                appendix_active = bool(appendix_match)
                special_content = bool(appendix_match or re.search(r"revision|change history", text, re.I))
            elif appendix_active and len(text) <= 120 and not text.endswith((".", ";", ",")):
                blocks.append(ExtractedBlock(kind="heading", text=text, order=order, level=2,
                                             structured={"style": paragraph.style.name, "appendix": True}))
                appendix_active = False
            elif style.startswith("list") or _LIST_ITEM.match(paragraph.text):
                blocks.append(ExtractedBlock(kind="list", text=text, order=order,
                                             structured={"style": paragraph.style.name}))
            elif not seen_heading:
                blocks.append(ExtractedBlock(kind="document_metadata", text=text, order=order,
                                             semantic=False, structured={"style": paragraph.style.name}))
            else:
                blocks.append(ExtractedBlock(
                    kind="appendix_revision" if special_content else "paragraph",
                    text=text, order=order,
                    structured={"contentType": "appendix_or_revision"} if special_content else {},
                ))
            order += 1

        elif tag == "tbl":
            table = Table(child, document)
            rows = [
                " | ".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
                if any(cell.text.strip() for cell in row.cells)
            ]
            if rows:
                cells = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                opening_approval = not seen_heading and any(
                    token in " ".join(rows).lower() for token in ("signature", "name", "date", "approval")
                )
                # Kept as one block so chunking can never split a table.
                blocks.append(ExtractedBlock(
                    kind="approval_signature" if opening_approval else "table",
                    text="\n".join(rows), order=order, semantic=not opening_approval,
                    structured={"rows": cells, "tableType": "approval" if opening_approval else "content"},
                ))
                order += 1

    warnings = [] if blocks else ["The document contains no readable text."]
    return ExtractedDocument(
        blocks=blocks, page_count=0, source_format="docx", warnings=warnings
    )
