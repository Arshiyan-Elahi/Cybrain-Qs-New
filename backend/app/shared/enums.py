from enum import StrEnum


class KnowledgeTier(StrEnum):
    """
    Trust layers. Tier travels with a fact through retrieval, prompt, draft and
    UI; industry or global content is never presented as the company's own
    verified knowledge (CLAUDE.md §4).
    """

    COMPANY = "company"
    INDUSTRY = "industry"
    GLOBAL = "global"


class KnowledgeStatus(StrEnum):
    """
    AI output enters as `proposed` and only a human action moves it to
    `verified`. There is no automatic promotion path.
    """

    PROPOSED = "proposed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class KnowledgeType(StrEnum):
    TERMINOLOGY = "terminology"
    ROLE = "role"
    PROCESS = "process"
    REGULATION = "regulation"
    DOCUMENT_STANDARD = "document_standard"
    WRITING_STYLE = "writing_style"
    FORM_OR_RECORD = "form_or_record"
    DOCUMENT_STRUCTURE = "document_structure"
    WORKFLOW = "workflow"
    BUSINESS_RULE = "business_rule"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"
    CANCELLED = "cancelled"


class DocumentKind(StrEnum):
    GENERAL = "general"
    SOP = "sop"
    TEMPLATE = "template"
