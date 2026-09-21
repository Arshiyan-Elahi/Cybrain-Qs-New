import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import (
    company_id_var,
    get_logger,
    log_event,
    logging_flags,
    maybe_content,
    reset_llm_call_context,
    set_llm_call_context,
)
from app.integrations.llm.base import ChatMessage, LLMProvider
from app.modules.companies.models import CompanyOnboardingProfile
from app.modules.companies.service import CompanyService
from app.modules.documents.cancellation import check_cancelled
from app.modules.documents.models import Document, DocumentChunk
from app.modules.knowledge.models import KnowledgeObject, KnowledgeObjectHistory
from app.modules.knowledge.semantic_extract import (
    CKM_EXTRACT_PROMPT_VERSION,
    CKM_EXTRACT_SYSTEM,
    semantic_candidates,
)
from app.modules.knowledge.terminology import (
    TERM_PATTERNS,
    occurrence_count,
    select_terminology_chunk,
)
from app.shared.enums import KnowledgeSourceKind, KnowledgeStatus, KnowledgeTier

logger = get_logger("app.knowledge")

DOCUMENT_EXTRACTION_VERSION = 5
DOCUMENT_SCOPE_LOCATION = "document"
_DOCUMENT_EXTRACT_METHODS = frozenset(
    {"deterministic", "local-llm", "local-llm-document"}
)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
LINE_SPLIT_RE = re.compile(r"[\n;•]+|(?:,\s+)(?=[A-Z])")


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
        *,
        type: str | None = None,
        status: str | None = None,
        source_kind: str | None = None,
        source_document_id: uuid.UUID | None = None,
        origin: str | None = None,
        include_superseded: bool = False,
    ) -> tuple[list[KnowledgeObject], int]:
        self.companies.get(user_id, company_id)
        base = select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)
        if type:
            base = base.where(KnowledgeObject.type == type)
        if status:
            base = base.where(KnowledgeObject.status == status)
        elif not include_superseded:
            base = base.where(KnowledgeObject.status != KnowledgeStatus.SUPERSEDED)
        if source_kind:
            base = base.where(KnowledgeObject.source_kind == source_kind)
        if origin == "onboarding":
            base = base.where(KnowledgeObject.source_kind == KnowledgeSourceKind.ONBOARDING)
        elif origin == "document":
            base = base.where(
                KnowledgeObject.source_kind.in_(
                    [KnowledgeSourceKind.UPLOADED_DOCUMENT, KnowledgeSourceKind.AI_EXTRACTED]
                )
            )
        if source_document_id is not None:
            base = base.where(KnowledgeObject.source_document_id == source_document_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        page = base.order_by(KnowledgeObject.created_at.desc()).limit(limit).offset(offset)
        items = list(self.db.scalars(page).all())
        self._attach_document_names(items)
        return items, int(total or 0)

    def history(
        self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID
    ) -> list[KnowledgeObjectHistory]:
        item = self.get(user_id, company_id, object_id)
        rows = list(
            self.db.scalars(
                select(KnowledgeObjectHistory)
                .where(
                    KnowledgeObjectHistory.company_id == company_id,
                    KnowledgeObjectHistory.knowledge_object_id.in_(
                        self._revision_ids(company_id, item)
                    ),
                )
                .order_by(KnowledgeObjectHistory.created_at.asc())
            ).all()
        )
        return rows

    def _revision_ids(self, company_id: uuid.UUID, item: KnowledgeObject) -> list[uuid.UUID]:
        ids = [item.id]
        cursor = item.supersedes_id
        seen: set[uuid.UUID] = {item.id}
        while cursor and cursor not in seen:
            seen.add(cursor)
            ids.append(cursor)
            parent = self.db.scalar(
                select(KnowledgeObject).where(
                    KnowledgeObject.id == cursor,
                    KnowledgeObject.company_id == company_id,
                )
            )
            cursor = parent.supersedes_id if parent else None
        children = list(
            self.db.scalars(
                select(KnowledgeObject.id).where(
                    KnowledgeObject.company_id == company_id,
                    KnowledgeObject.supersedes_id.in_(ids),
                )
            ).all()
        )
        return list({*ids, *children})

    def _attach_document_names(self, items: list[KnowledgeObject]) -> None:
        ids = {item.source_document_id for item in items if item.source_document_id}
        names = (
            dict(
                self.db.execute(select(Document.id, Document.filename).where(Document.id.in_(ids)))
                .tuples()
                .all()
            )
            if ids
            else {}
        )
        for item in items:
            if item.source_document_id:
                item.source_document_name = names.get(item.source_document_id, "Source document")
            elif item.source_kind == KnowledgeSourceKind.ONBOARDING:
                item.source_document_name = "Company onboarding"
            else:
                item.source_document_name = "Human entry"

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

    def _record_history(
        self,
        item: KnowledgeObject,
        action: str,
        actor_id: uuid.UUID | None,
        detail: str | None = None,
    ) -> None:
        evidence = item.payload.get("evidence", []) if isinstance(item.payload, dict) else []
        self.db.add(
            KnowledgeObjectHistory(
                company_id=item.company_id,
                knowledge_object_id=item.id,
                action=action,
                actor_id=actor_id,
                label=item.label,
                status=item.status,
                source_kind=item.source_kind,
                version=item.version,
                evidence_snapshot=list(evidence) if isinstance(evidence, list) else [],
                payload_snapshot=dict(item.payload) if isinstance(item.payload, dict) else {},
                detail=detail,
            )
        )

    def confirm(self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID) -> KnowledgeObject:
        item = self.get(user_id, company_id, object_id)
        if item.status != KnowledgeStatus.PROPOSED:
            raise ConflictError("Only proposed Knowledge Objects can be confirmed.")
        item.status = KnowledgeStatus.VERIFIED
        item.verified_by = user_id
        item.verified_at = datetime.now(timezone.utc)
        self._record_history(item, "confirmed", user_id)
        self.db.flush()
        log_event(
            logger,
            "ckm_object_confirmed",
            "Knowledge Object confirmed",
            company_id=str(company_id),
            object_id=str(object_id),
            type=item.type,
            label=item.label[:120],
        )
        return item

    def reject(self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID) -> KnowledgeObject:
        item = self.get(user_id, company_id, object_id)
        if item.status != KnowledgeStatus.PROPOSED:
            raise ConflictError("Only proposed Knowledge Objects can be rejected.")
        item.status = KnowledgeStatus.REJECTED
        item.rejected_by = user_id
        item.rejected_at = datetime.now(timezone.utc)
        self._record_history(item, "rejected", user_id)
        self.db.flush()
        log_event(
            logger,
            "ckm_object_rejected",
            "Knowledge Object rejected",
            company_id=str(company_id),
            object_id=str(object_id),
            type=item.type,
            label=item.label[:120],
        )
        return item

    def edit(
        self, user_id: uuid.UUID, company_id: uuid.UUID, object_id: uuid.UUID, label: str
    ) -> KnowledgeObject:
        item = self.get(user_id, company_id, object_id)
        if item.status == KnowledgeStatus.REJECTED:
            raise ConflictError("Rejected Knowledge Objects cannot be edited.")
        if item.status == KnowledgeStatus.SUPERSEDED:
            raise ConflictError("Superseded Knowledge Objects cannot be edited.")
        if item.status == KnowledgeStatus.VERIFIED:
            # Preserve the verified row and its evidence; revision is a new proposed object.
            replacement = KnowledgeObject(
                company_id=item.company_id,
                type=item.type,
                tier=item.tier,
                status=KnowledgeStatus.PROPOSED,
                label=label,
                payload={
                    **dict(item.payload),
                    "priorVerifiedBy": str(item.verified_by) if item.verified_by else None,
                    "priorVerifiedAt": item.verified_at.isoformat() if item.verified_at else None,
                    "priorLabel": item.label,
                },
                source_kind=KnowledgeSourceKind.HUMAN_CREATED,
                source_document_id=item.source_document_id,
                source_chunk_id=item.source_chunk_id,
                source_location=item.source_location,
                extraction_method="human-edit",
                model_name=item.model_name,
                model_provider=item.model_provider,
                extracted_at=datetime.now(timezone.utc),
                version=item.version + 1,
                supersedes_id=item.id,
            )
            self._attach_document_names([replacement])
            item.status = KnowledgeStatus.SUPERSEDED
            self._record_history(item, "superseded", user_id, detail=f"Replaced by edit: {label}")
            self.db.add(replacement)
            self.db.flush()
            self._record_history(replacement, "proposed_created", user_id, detail="human-edit of verified")
            self.db.flush()
            log_event(
                logger,
                "ckm_object_edited",
                "Verified Knowledge Object superseded by edit",
                company_id=str(company_id),
                object_id=str(replacement.id),
                supersedes_id=str(item.id),
                type=replacement.type,
            )
            return replacement
        prior = item.label
        item.label = label
        item.extraction_method = "human-edit"
        if item.source_kind in (
            KnowledgeSourceKind.AI_EXTRACTED,
            KnowledgeSourceKind.UPLOADED_DOCUMENT,
            KnowledgeSourceKind.ONBOARDING,
        ):
            # Human corrected the proposed text; provenance origin stays, method records edit.
            pass
        self._record_history(item, "edited", user_id, detail=f"{prior} → {label}")
        self.db.flush()
        log_event(
            logger,
            "ckm_object_edited",
            "Knowledge Object edited",
            company_id=str(company_id),
            object_id=str(object_id),
            type=item.type,
        )
        return item

    def propose_from_onboarding(self, user_id: uuid.UUID, company_id: uuid.UUID) -> int:
        """Convert persisted onboarding answers into proposed Knowledge Objects."""
        company = self.companies.get(user_id, company_id)
        profile = self.db.get(CompanyOnboardingProfile, company.id)
        if profile is None:
            return 0

        existing_items = list(
            self.db.scalars(
                select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)
            ).all()
        )
        by_canonical = {
            str(item.payload.get("canonicalKey")): item
            for item in existing_items
            if isinstance(item.payload, dict) and item.payload.get("canonicalKey")
        }
        by_type_label = {
            (item.type, item.label.casefold()): item
            for item in existing_items
            if item.status != KnowledgeStatus.REJECTED
        }

        created = 0
        for kind, label, field, body in self._onboarding_candidates(profile):
            canonical = f"onboarding:{field}:{label.casefold()}"
            if canonical in by_canonical:
                continue
            key = (kind, label.casefold())
            if key in by_type_label:
                continue
            evidence = [
                {
                    "origin": KnowledgeSourceKind.ONBOARDING,
                    "field": field,
                    "snippet": body[:500],
                }
            ]
            pending = KnowledgeObject(
                company_id=company_id,
                type=kind,
                tier=KnowledgeTier.COMPANY,
                status=KnowledgeStatus.PROPOSED,
                label=label[:500],
                payload={
                    "field": field,
                    "text": body,
                    "canonicalKey": canonical,
                    "evidence": evidence,
                    "extractionVersion": 2,
                },
                source_kind=KnowledgeSourceKind.ONBOARDING,
                source_document_id=None,
                source_chunk_id=None,
                source_location=f"onboarding.{field}",
                extraction_method="onboarding-profile",
                model_name=None,
                model_provider=None,
                extracted_at=datetime.now(timezone.utc),
            )
            self.db.add(pending)
            self.db.flush()
            self._record_history(pending, "proposed_created", user_id, detail="onboarding")
            by_canonical[canonical] = pending
            by_type_label[key] = pending
            created += 1
        self.db.flush()
        return created

    @classmethod
    def _onboarding_candidates(cls, profile: CompanyOnboardingProfile):
        candidates: list[tuple[str, str, str, str]] = []

        def add_lines(kind: str, field: str, text: str) -> None:
            for part in cls._split_answers(text):
                candidates.append((kind, part, field, part))

        add_lines("terminology", "terminology_text", profile.terminology_text)
        if profile.prefer_existing_terms:
            candidates.append(
                (
                    "terminology",
                    "Prefer existing company terminology",
                    "prefer_existing_terms",
                    "prefer_existing_terms=true",
                )
            )
        add_lines("role", "roles_text", profile.roles_text)
        add_lines("responsibility", "departments_text", profile.departments_text)
        add_lines("process", "processes_text", profile.processes_text)
        add_lines("workflow", "workflow_notes", profile.workflow_notes)
        add_lines("business_rule", "business_rules_text", profile.business_rules_text)
        add_lines("form_or_record", "forms_text", profile.forms_text)
        add_lines("relationship", "relationships_text", profile.relationships_text)
        add_lines("best_practice", "best_practices_text", profile.best_practices_text)

        structure_bits = [
            bit
            for bit in (
                profile.structure_preference_id,
                profile.document_structure_notes,
                profile.template_preference_id,
                profile.layout_notes,
            )
            if bit and str(bit).strip()
        ]
        if structure_bits:
            label = structure_bits[0][:500] if len(structure_bits) == 1 else "Document structure preferences"
            candidates.append(
                ("document_structure", label, "document_structure", " | ".join(structure_bits))
            )

        writing_bits = [
            bit
            for bit in (
                profile.tone_id,
                profile.formality_id,
                profile.person_id,
                profile.writing_notes,
            )
            if bit and str(bit).strip()
        ]
        if writing_bits:
            label = writing_bits[0][:500] if len(writing_bits) == 1 else "Writing style preferences"
            candidates.append(("writing_style", label, "writing_style", " | ".join(writing_bits)))

        if profile.ai_assist_level_id or profile.quality_notes or profile.require_human_verification:
            body = (
                f"ai_assist={profile.ai_assist_level_id}; "
                f"require_human_verification={profile.require_human_verification}; "
                f"{profile.quality_notes}"
            ).strip()
            candidates.append(
                (
                    "ai_preference",
                    profile.ai_assist_level_id or "AI / quality preferences",
                    "ai_quality_preferences",
                    body,
                )
            )

        # Deduplicate within this batch by type+label.
        seen: set[tuple[str, str]] = set()
        unique: list[tuple[str, str, str, str]] = []
        for row in candidates:
            key = (row[0], row[1].casefold())
            if key in seen or not row[1].strip():
                continue
            seen.add(key)
            unique.append(row)
        return unique

    @staticmethod
    def _split_answers(text: str) -> list[str]:
        if not text or not text.strip():
            return []
        parts = [p.strip(" -\t") for p in LINE_SPLIT_RE.split(text) if p and p.strip(" -\t")]
        return [p[:500] for p in parts if len(p) >= 2]

    def extract_from_chunks(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        llm: LLMProvider,
        cancel_token: threading.Event | None = None,
    ) -> tuple[int, int]:
        """Analyze persisted chunks only; extraction/chunking is never invoked here."""
        import time
        from collections import Counter

        company_id_var.set(str(company_id))
        started = time.perf_counter()
        log_event(
            logger,
            "ckm_extraction_started",
            "CKM extraction started",
            company_id=str(company_id),
        )
        self.companies.get(user_id, company_id)
        chunks = list(
            self.db.scalars(
                select(DocumentChunk)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.company_id == company_id)
                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_order)
            ).all()
        )
        existing_items = list(
            self.db.scalars(select(KnowledgeObject).where(KnowledgeObject.company_id == company_id)).all()
        )
        existing = {(item.type, item.label.casefold()): item for item in existing_items}
        created = 0
        skipped = 0
        documents: dict[uuid.UUID, list[DocumentChunk]] = {}
        for chunk in chunks:
            documents.setdefault(chunk.document_id, []).append(chunk)
        filenames = dict(
            self.db.execute(
                select(Document.id, Document.filename).where(Document.company_id == company_id)
            )
            .tuples()
            .all()
        )
        type_counts: Counter[str] = Counter()
        last_completion = None
        for document_id, document_chunks in documents.items():
            check_cancelled(cancel_token)
            analysis_hash = self._analysis_hash(document_chunks)
            document_key = str(document_id)
            legacy = [
                item
                for item in existing_items
                if item.source_document_id == document_id
                and item.status == KnowledgeStatus.PROPOSED
                and item.extraction_method in _DOCUMENT_EXTRACT_METHODS
                and item.payload.get("extractionVersion") != DOCUMENT_EXTRACTION_VERSION
            ]
            for item in legacy:
                self.db.delete(item)
                existing.pop((item.type, item.label.casefold()), None)
                existing_items.remove(item)
            if any(
                item.source_document_id == document_id
                and item.status == KnowledgeStatus.PROPOSED
                and item.payload.get("extractionVersion") == DOCUMENT_EXTRACTION_VERSION
                and item.payload.get("analysisHashes", {}).get(document_key) == analysis_hash
                for item in existing_items
            ):
                skipped += 1
                continue
            candidates = self._deterministic_candidates(
                document_chunks, filenames[document_id], analysis_hash
            )
            semantic_chunks = [c for c in document_chunks if c.is_semantic and c.heading_path]
            compact_chunks = [
                {"id": str(c.id), "section": c.heading_path, "text": c.text} for c in semantic_chunks
            ]
            ctx_token = set_llm_call_context(
                operation="ckm_extraction",
                prompt_version=CKM_EXTRACT_PROMPT_VERSION,
                retrieved_chunk_ids=[str(c.id) for c in semantic_chunks[:20]],
            )
            try:
                completion = llm.complete(
                    [
                        ChatMessage(role="system", content=CKM_EXTRACT_SYSTEM),
                        ChatMessage(role="user", content=json.dumps(compact_chunks, separators=(",", ":"))),
                    ],
                    temperature=0.0,
                    max_tokens=8192,
                )
            finally:
                reset_llm_call_context(ctx_token)
            check_cancelled(cancel_token)
            last_completion = completion
            llm_rows, parse_diag = semantic_candidates(
                completion.text, semantic_chunks, analysis_hash
            )
            self._log_llm_parse(completion, parse_diag)
            candidates.extend(llm_rows)
            candidate_keys: set[tuple[str, str]] = set()
            for kind, label, payload, method, source_chunk in candidates:
                candidate_key = (kind, label.casefold())
                if candidate_key in candidate_keys:
                    continue
                candidate_keys.add(candidate_key)
                source_kind = (
                    KnowledgeSourceKind.AI_EXTRACTED
                    if method.startswith("local-llm")
                    else KnowledgeSourceKind.UPLOADED_DOCUMENT
                )
                if source_chunk is None:
                    evidence = {
                        "documentId": str(document_id),
                        "documentName": filenames[document_id],
                        "scope": "document",
                    }
                    chunk_id = None
                    source_location = DOCUMENT_SCOPE_LOCATION
                    tier = KnowledgeTier.COMPANY
                else:
                    evidence = {
                        "documentId": str(document_id),
                        "documentName": filenames[document_id],
                        "section": source_chunk.heading_path,
                        "snippet": source_chunk.text[:500],
                        "chunkId": str(source_chunk.id),
                    }
                    chunk_id = source_chunk.id
                    source_location = source_chunk.location
                    tier = source_chunk.tier
                prior = existing.get(candidate_key)
                if prior is not None:
                    if prior.status != KnowledgeStatus.PROPOSED:
                        continue
                    evidences = list(prior.payload.get("evidence", []))
                    if not any(
                        entry.get("documentId") == str(document_id)
                        and entry.get("chunkId") == (str(chunk_id) if chunk_id else None)
                        and entry.get("scope") == evidence.get("scope")
                        for entry in evidences
                    ):
                        prior.payload = {
                            **prior.payload,
                            "evidence": [*evidences, evidence],
                            "analysisHashes": {
                                **prior.payload.get("analysisHashes", {}),
                                document_key: analysis_hash,
                            },
                        }
                    continue
                payload = {
                    **payload,
                    "evidence": [evidence],
                    "analysisHashes": {document_key: analysis_hash},
                    "extractionVersion": DOCUMENT_EXTRACTION_VERSION,
                }
                pending = KnowledgeObject(
                    company_id=company_id,
                    type=kind,
                    tier=tier,
                    status=KnowledgeStatus.PROPOSED,
                    label=label,
                    payload=payload,
                    source_kind=source_kind,
                    source_document_id=document_id,
                    source_chunk_id=chunk_id,
                    source_location=source_location,
                    extraction_method=method,
                    model_name=last_completion.model if method.startswith("local-llm") and last_completion else None,
                    model_provider=last_completion.provider if method.startswith("local-llm") and last_completion else None,
                    extracted_at=datetime.now(timezone.utc),
                )
                self.db.add(pending)
                self.db.flush()
                self._record_history(pending, "proposed_created", user_id, detail=method)
                existing[candidate_key] = pending
                existing_items.append(pending)
                created += 1
                type_counts[kind] += 1
        check_cancelled(cancel_token)
        self.db.flush()
        log_event(
            logger,
            "ckm_extraction_completed",
            "CKM extraction completed",
            company_id=str(company_id),
            proposed_created=created,
            skipped=skipped,
            type_counts=dict(type_counts),
            document_count=len(documents),
            latency_ms=int((time.perf_counter() - started) * 1000),
            provider=(last_completion.provider if last_completion else getattr(llm, "name", None)),
            model=(last_completion.model if last_completion else getattr(llm, "chat_model", None)),
        )
        return created, skipped

    def _log_llm_parse(self, completion, parse_diag: dict) -> None:
        from app.core.config import get_settings

        flags = logging_flags()
        settings = get_settings()
        usage = completion.usage or {}
        fields = {
            "provider": completion.provider,
            "model": completion.model,
            "prompt_version": CKM_EXTRACT_PROMPT_VERSION,
            "response_chars": parse_diag.get("response_chars"),
            "json_root_type": parse_diag.get("json_root_type"),
            "parse_ok": parse_diag.get("parse_ok"),
            "parse_error": parse_diag.get("parse_error"),
            "unwrapped": parse_diag.get("unwrapped"),
            "repaired": parse_diag.get("repaired"),
            "raw_item_count": parse_diag.get("raw_item_count"),
            "kept": parse_diag.get("kept"),
            "finish_reason": usage.get("finish_reason"),
            "thought_parts": usage.get("thought_parts"),
        }
        dropped = parse_diag.get("dropped")
        if isinstance(dropped, dict):
            fields["dropped"] = {key: value for key, value in dropped.items() if value}
        if settings.environment != "production" or flags.get("log_ai_content"):
            fields["response_preview"] = maybe_content(
                completion.text,
                enabled=True,
                max_chars=min(int(flags.get("log_ai_content_max_chars", 2000)), 500),
            )
        log_event(logger, "ckm_llm_parse", "CKM LLM response parsed", **fields)

    @staticmethod
    def _analysis_hash(chunks: list[DocumentChunk]) -> str:
        material = "\n".join(f"{c.id}:{c.chunk_order}:{c.text}" for c in chunks)
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _deterministic_candidates(
        chunks: list[DocumentChunk], filename: str, analysis_hash: str
    ) -> list[tuple[str, str, dict, str, DocumentChunk | None]]:
        text = " ".join(c.text for c in chunks)
        sentences = [s for s in SENTENCE_RE.split(text) if s.strip()]
        unique_paths = []
        seen_paths = set()
        for chunk in chunks:
            path = tuple(chunk.heading_path)
            if path and path not in seen_paths:
                seen_paths.add(path)
                unique_paths.append(list(path))
        result: list[tuple[str, str, dict, str, DocumentChunk | None]] = [
            (
                "document_structure",
                f"{filename} structure",
                {
                    "headingPaths": unique_paths,
                    "headingCount": len(unique_paths),
                    "chunkCount": len(chunks),
                    "scope": "document",
                },
                "deterministic",
                None,
            )
        ]
        modals = {word: len(re.findall(rf"\b{word}\b", text, re.I)) for word in ("shall", "must", "should", "may")}
        result.append(
            (
                "writing_style",
                f"{filename} writing statistics",
                {
                    "sentenceCount": len(sentences),
                    "averageWordsPerSentence": round(
                        sum(len(s.split()) for s in sentences) / max(len(sentences), 1), 1
                    ),
                    "modalCounts": modals,
                    "scope": "document",
                },
                "deterministic",
                None,
            )
        )
        for term, pattern in TERM_PATTERNS.items():
            count = occurrence_count(text, pattern)
            source = select_terminology_chunk(chunks, pattern)
            if count and source is not None:
                result.append(
                    (
                        "terminology",
                        term,
                        {"occurrenceCount": count},
                        "deterministic",
                        source,
                    )
                )
        return result
