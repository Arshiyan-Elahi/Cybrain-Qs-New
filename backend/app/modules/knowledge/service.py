import json
import re
import uuid
import threading
import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.companies.service import CompanyService
from app.modules.knowledge.models import KnowledgeObject
from app.modules.documents.models import Document, DocumentChunk
from app.integrations.llm.base import ChatMessage, LLMProvider
from app.core.errors import ConflictError, NotFoundError
from app.shared.enums import KnowledgeStatus
from app.modules.documents.cancellation import check_cancelled

SEMANTIC_TYPES = {"regulation", "role", "responsibility", "workflow", "process", "business_rule", "form_or_record", "relationship"}
TERM_PATTERNS = {
    "Standard Operating Procedure (SOP)": r"\b(?:Standard Operating Procedures?|SOPs?)\b",
    "Work Instruction (WI)": r"\b(?:Work Instructions?|WIs?)\b",
    "Quality Assurance (QA)": r"\b(?:Quality Assurance|QA)\b",
    "Good Manufacturing Practice (GMP)": r"\b(?:Good Manufacturing Practices?|GMP)\b",
    "Good Clinical Practice (GCP)": r"\b(?:Good Clinical Practice|GCP)\b",
    "Quality Management System (QMS)": r"\b(?:Quality Management System|QMS)\b",
    "On-the-Job Training (OJT)": r"\b(?:On-the-Job Training|On the Job Training|OJT)\b",
}
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class KnowledgeService:
    def __init__(self, db: Session, companies: CompanyService) -> None:
        self.db = db
        self.companies = companies

    def list(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[KnowledgeObject], int]:
        self.companies.get(user_id, company_id)
        base = select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        page = base.order_by(KnowledgeObject.created_at.desc()).limit(limit).offset(offset)
        items = list(self.db.scalars(page).all())
        self._attach_document_names(items)
        return items, int(total or 0)

    def _attach_document_names(self, items: list[KnowledgeObject]) -> None:
        ids = {item.source_document_id for item in items}
        names = dict(self.db.execute(select(Document.id, Document.filename).where(Document.id.in_(ids))).tuples().all()) if ids else {}
        for item in items:
            item.source_document_name = names.get(item.source_document_id, "Source document")

    def get(self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID) -> KnowledgeObject:
        self.companies.get(user_id, company_id)
        item = self.db.scalar(
            select(KnowledgeObject).where(
                KnowledgeObject.id == object_id,
                KnowledgeObject.company_id == company_id,
            )
        )
        if item is None:
            raise NotFoundError("Knowledge Object not found.")
        self._attach_document_names([item])
        return item

    def confirm(self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID) -> KnowledgeObject:
        item = self.get(user_id, company_id, object_id)
        if item.status != KnowledgeStatus.PROPOSED:
            raise ConflictError("Only proposed Knowledge Objects can be confirmed.")
        item.status = KnowledgeStatus.VERIFIED
        item.verified_by = user_id
        item.verified_at = datetime.now(timezone.utc)
        self.db.flush()
        return item

    def reject(self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID) -> KnowledgeObject:
        item = self.get(user_id, company_id, object_id)
        if item.status != KnowledgeStatus.PROPOSED:
            raise ConflictError("Only proposed Knowledge Objects can be rejected.")
        item.status = KnowledgeStatus.REJECTED
        self.db.flush()
        return item

    def edit(
        self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID, label: str
    ) -> KnowledgeObject:
        item = self.get(user_id, company_id, object_id)
        if item.status == KnowledgeStatus.REJECTED:
            raise ConflictError("Rejected Knowledge Objects cannot be edited.")
        if item.status == KnowledgeStatus.VERIFIED:
            replacement = KnowledgeObject(
                company_id=item.company_id, type=item.type, tier=item.tier,
                status=KnowledgeStatus.PROPOSED, label=label, payload=dict(item.payload),
                source_document_id=item.source_document_id, source_chunk_id=item.source_chunk_id,
                source_location=item.source_location, extraction_method="human-edit",
                model_name=item.model_name, model_provider=item.model_provider,
                extracted_at=datetime.now(timezone.utc), version=item.version + 1,
            )
            replacement.source_document_name = item.source_document_name
            item.status = KnowledgeStatus.SUPERSEDED
            self.db.add(replacement)
            self.db.flush()
            return replacement
        item.label = label
        item.extraction_method = "human-edit"
        self.db.flush()
        return item

    def extract_from_chunks(
        self, user_id: uuid.UUID, company_id: uuid.UUID, llm: LLMProvider,
        cancel_token: threading.Event | None = None,
    ) -> tuple[int, int]:
        """Analyze persisted chunks only; extraction/chunking is never invoked here."""
        self.companies.get(user_id, company_id)
        chunks = list(self.db.scalars(
            select(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.company_id == company_id)
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_order)
        ).all())
        existing_items = list(self.db.scalars(select(KnowledgeObject).where(
            KnowledgeObject.company_id == company_id
        )).all())
        existing = {(item.type, item.label.casefold()): item for item in existing_items}
        created = 0
        skipped = 0
        documents: dict[uuid.UUID, list[DocumentChunk]] = {}
        for chunk in chunks:
            documents.setdefault(chunk.document_id, []).append(chunk)
        filenames = dict(self.db.execute(select(Document.id, Document.filename).where(
            Document.company_id == company_id
        )).tuples().all())
        for document_id, document_chunks in documents.items():
            check_cancelled(cancel_token)
            analysis_hash = self._analysis_hash(document_chunks)
            document_key = str(document_id)
            legacy = [item for item in existing_items if item.source_document_id == document_id
                      and item.status == KnowledgeStatus.PROPOSED
                      and item.extraction_method in ("deterministic", "local-llm", "local-llm-document")
                      and item.payload.get("extractionVersion") != 2]
            for item in legacy:
                self.db.delete(item)
                existing.pop((item.type, item.label.casefold()), None)
                existing_items.remove(item)
            if any(item.payload.get("analysisHashes", {}).get(document_key) == analysis_hash
                   for item in existing_items):
                skipped += 1
                continue
            candidates = self._deterministic_candidates(document_chunks, filenames[document_id], analysis_hash)
            semantic_chunks = [c for c in document_chunks if c.is_semantic and c.heading_path]
            compact_chunks = [{"id": str(c.id), "section": c.heading_path, "text": c.text} for c in semantic_chunks]
            completion = llm.complete([
                ChatMessage(role="system", content=(
                    "Extract supported SOP knowledge. Return only a JSON array of objects with "
                    "type, label, sourceChunkId, payload. Types: regulation, role, responsibility, workflow, "
                    "process, business_rule, form_or_record, relationship. Use only explicit supplied text; "
                    "labels must be concise; omit unsupported items."
                )),
                ChatMessage(role="user", content=json.dumps(compact_chunks, separators=(",", ":"))),
            ], temperature=0.0, max_tokens=1200)
            check_cancelled(cancel_token)
            candidates.extend(self._semantic_candidates(completion.text, semantic_chunks, analysis_hash))
            candidate_keys: set[tuple[str, str]] = set()
            for kind, label, payload, method, source_chunk in candidates:
                candidate_key = (kind, label.casefold())
                if candidate_key in candidate_keys:
                    continue
                candidate_keys.add(candidate_key)
                evidence = {"documentId": str(document_id), "documentName": filenames[document_id],
                            "section": source_chunk.heading_path, "snippet": source_chunk.text[:500],
                            "chunkId": str(source_chunk.id)}
                prior = existing.get(candidate_key)
                if prior is not None:
                    evidences = list(prior.payload.get("evidence", []))
                    if not any(entry.get("documentId") == str(document_id) and entry.get("chunkId") == str(source_chunk.id) for entry in evidences):
                        prior.payload = {**prior.payload, "evidence": [*evidences, evidence],
                                         "analysisHashes": {**prior.payload.get("analysisHashes", {}), document_key: analysis_hash}}
                    continue
                payload = {**payload, "evidence": [evidence], "analysisHashes": {document_key: analysis_hash},
                           "extractionVersion": 2}
                pending = KnowledgeObject(
                    company_id=company_id, type=kind, tier=source_chunk.tier,
                    status=KnowledgeStatus.PROPOSED, label=label, payload=payload,
                    source_document_id=document_id, source_chunk_id=source_chunk.id,
                    source_location=source_chunk.location, extraction_method=method,
                    model_name=completion.model if method.startswith("local-llm") else None,
                    model_provider=completion.provider if method.startswith("local-llm") else None,
                    extracted_at=datetime.now(timezone.utc),
                )
                self.db.add(pending)
                existing[candidate_key] = pending
                existing_items.append(pending)
                created += 1
        check_cancelled(cancel_token)
        self.db.flush()
        return created, skipped

    @staticmethod
    def _analysis_hash(chunks: list[DocumentChunk]) -> str:
        material = "\n".join(f"{c.id}:{c.chunk_order}:{c.text}" for c in chunks)
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _deterministic_candidates(chunks: list[DocumentChunk], filename: str, analysis_hash: str):
        # Document-level observations still need meaningful provenance.  The
        # first persisted block can be an approval/metadata block with no
        # semantic section, so anchor them to the first semantic section.
        first = next((chunk for chunk in chunks if chunk.is_semantic and chunk.heading_path), chunks[0])
        text = " ".join(c.text for c in chunks)
        sentences = [s for s in SENTENCE_RE.split(text) if s.strip()]
        common = {}
        unique_paths = []
        seen_paths = set()
        for chunk in chunks:
            path = tuple(chunk.heading_path)
            if path and path not in seen_paths:
                seen_paths.add(path)
                unique_paths.append(list(path))
        result = [("document_structure", f"{filename} structure", {
            **common, "headingPaths": unique_paths, "headingCount": len(unique_paths), "chunkCount": len(chunks),
        }, "deterministic", first)]
        modals = {word: len(re.findall(rf"\b{word}\b", text, re.I)) for word in ("shall", "must", "should", "may")}
        result.append(("writing_style", f"{filename} writing statistics", {
            **common, "sentenceCount": len(sentences),
            "averageWordsPerSentence": round(sum(len(s.split()) for s in sentences) / max(len(sentences), 1), 1),
            "modalCounts": modals,
        }, "deterministic", first))
        for term, pattern in TERM_PATTERNS.items():
            count = len(re.findall(pattern, text, re.I))
            if count:
                source = next((chunk for chunk in chunks if chunk.heading_path and re.search(pattern, chunk.text, re.I)), first)
                result.append(("terminology", term, {**common, "count": count}, "deterministic", source))
        return result

    @staticmethod
    def _semantic_candidates(raw: str, chunks: list[DocumentChunk], analysis_hash: str):
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        try:
            values = json.loads(cleaned)
        except (TypeError, json.JSONDecodeError):
            return []
        result = []
        by_id = {str(chunk.id): chunk for chunk in chunks}
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, dict) or value.get("type") not in SEMANTIC_TYPES:
                continue
            label = str(value.get("label", "")).strip()[:500]
            if label:
                payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
                source = by_id.get(str(value.get("sourceChunkId")))
                if source is None or not source.heading_path:
                    continue
                evidence = str(payload.pop("evidence", "")).strip()
                if evidence and evidence.casefold() not in source.text.casefold():
                    continue
                result.append((value["type"], label, payload, "local-llm-document", source))
        return result
