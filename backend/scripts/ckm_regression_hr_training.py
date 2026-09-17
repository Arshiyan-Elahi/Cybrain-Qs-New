"""
Real end-to-end CKM regression for SOP-HR-001 (Qualification Training).

Property-based checks only — no hardcoded production counts or labels.
Uses an ephemeral Postgres database matching current SQLAlchemy models.

    python scripts/ckm_regression_hr_training.py [path-to-docx]
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.integrations.llm.factory import get_llm_provider
from app.modules.auth.models import User, UserCompanyAccess
from app.modules.companies.models import Company, CompanyRegulation
from app.modules.companies.repository import CompanyRepository
from app.modules.companies.service import CompanyService
from app.modules.documents.ingestion import IngestionService
from app.modules.documents.models import DocumentChunk
from app.modules.knowledge.models import KnowledgeObject
from app.modules.knowledge.service import KnowledgeService, TERM_PATTERNS
from app.processing.chunker import chunk_document
from app.processing.extractor import extract
from app.shared.enums import DocumentStatus
from app.shared.registry import Base

DEFAULT_DOCX = Path(
    r"C:\Users\DilshadAli(ITOps)\Downloads\SOPs\SOPs\Client 1"
    r"\SOP-HR-001 V6 Qualification Training and Retraining of GxP personnel.docx"
)

JUNK_TERMS = {
    "NAME", "COMPANY", "II", "IV", "VI", "EU", "GMP-", "WI-LL-", "FRM-LL-",
    "DATE", "SIGNATURE", "PAGE", "VERSION", "REV", "N/A", "TBD",
}

CONCEPT_HINTS = {
    "QA": r"\b(?:Quality Assurance|QA)\b",
    "employees": r"\b(?:employee|employees|personnel|staff)\b",
    "trainers": r"\b(?:trainer|trainers|training coordinator)\b",
    "OJT": r"\b(?:On-the-Job Training|On the Job Training|OJT)\b",
    "retraining": r"\bretrain(?:ing|ed|s)?\b",
    "training records": r"\b(?:training record|training records|training documentation)\b",
}


def _find_docx(argv: list[str]) -> Path:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_DOCX
    if not path.is_file():
        raise SystemExit(f"DOCX not found: {path}")
    return path


def analyze_parser(content: bytes, filename: str) -> dict:
    extracted = extract(content, filename)
    chunks = chunk_document(extracted)
    semantic = [c for c in chunks if c.is_semantic]
    non_semantic = [c for c in chunks if not c.is_semantic]
    block_kinds = Counter(b.kind for b in extracted.blocks)
    table_chunks = [c for c in semantic if any(b["type"] == "table" for b in c.blocks)]
    list_blocks = sum(1 for b in extracted.blocks if b.kind == "list")
    heading_paths = [tuple(c.heading_path) for c in semantic]
    return {
        "filename": filename,
        "warnings": list(extracted.warnings),
        "page_count": extracted.page_count,
        "block_kinds": dict(block_kinds),
        "chunk_count": len(chunks),
        "semantic_chunk_count": len(semantic),
        "non_semantic_chunk_count": len(non_semantic),
        "table_chunk_count": len(table_chunks),
        "list_block_count": list_blocks,
        "unique_heading_paths": len(set(heading_paths)),
        "heading_paths_sample": [list(p) for p in heading_paths[:12]],
        "all_heading_paths": [list(p) for p in heading_paths],
        "missing_semantic_provenance": [c.order for c in semantic if not c.heading_path],
        "approval_chunks_in_semantic": [
            c.order for c in semantic
            if any(b["type"] == "approval_signature" for b in c.blocks)
        ],
        "non_semantic_kinds": sorted({b["type"] for c in non_semantic for b in c.blocks}),
        "full_text": "\n".join(c.text for c in chunks),
    }


def check_parser_invariants(report: dict) -> list[str]:
    failures: list[str] = []
    if report["chunk_count"] == 0:
        failures.append("parser produced zero chunks")
    if report["missing_semantic_provenance"]:
        failures.append(
            f"semantic chunks without heading_path: {report['missing_semantic_provenance']}"
        )
    if report["approval_chunks_in_semantic"]:
        failures.append(
            f"approval/header content leaked into semantic chunks: "
            f"{report['approval_chunks_in_semantic']}"
        )
    if report["block_kinds"].get("heading", 0) < 1:
        failures.append("no headings detected")
    if report["table_chunk_count"] < 1 and report["block_kinds"].get("table", 0) > 0:
        failures.append("tables extracted but not preserved as chunks")
    return failures


def source_supported_concepts(full_text: str) -> dict[str, bool]:
    import re

    return {
        name: bool(re.search(pattern, full_text, re.I))
        for name, pattern in CONCEPT_HINTS.items()
    }


def analyze_knowledge(items: list[KnowledgeObject], supported: dict[str, bool]) -> dict:
    by_type = Counter(item.type for item in items)
    labels_by_type: dict[str, list[str]] = {}
    for item in items:
        labels_by_type.setdefault(item.type, []).append(item.label)

    no_section = [
        {"type": item.type, "label": item.label, "location": item.source_location}
        for item in items
        if "(no section)" in (item.source_location or "")
    ]
    terminology = [item.label for item in items if item.type == "terminology"]
    junk = [
        label for label in terminology
        if label.strip().upper() in JUNK_TERMS or label.strip() in JUNK_TERMS
    ]
    junk.extend(
        label for label in terminology
        if label not in junk
        and (len(label.strip()) <= 2 or (label.strip().isupper() and len(label) <= 4))
        and label not in TERM_PATTERNS
    )

    key_counts = Counter((item.type, item.label.casefold()) for item in items)
    duplicates = [
        {"type": kind, "label": label, "count": count}
        for (kind, label), count in key_counts.items()
        if count > 1
    ]

    evidence_hits = {}
    for concept, present in supported.items():
        found = False
        if concept == "training records":
            found = any("training record" in (item.label or "").lower() for item in items) or any(
                item.type == "form_or_record" and "train" in (item.label or "").lower()
                for item in items
            )
        elif concept == "employees":
            found = any(
                token in (item.label or "").lower()
                for item in items
                for token in ("employee", "personnel", "staff")
            )
        elif concept == "trainers":
            found = any("trainer" in (item.label or "").lower() for item in items)
        elif concept == "retraining":
            found = any("retrain" in (item.label or "").lower() for item in items)
        elif concept == "OJT":
            found = any(
                "ojt" in (item.label or "").lower() or "on-the-job" in (item.label or "").lower()
                for item in items
            )
        elif concept == "QA":
            found = any(
                item.label in TERM_PATTERNS
                or "quality assurance" in (item.label or "").lower()
                or (item.label or "").strip().upper() == "QA"
                or (item.type == "role" and "qa" in (item.label or "").lower())
                for item in items
            )
        evidence_hits[concept] = {
            "supported_by_source": present,
            "present_in_ckm": found,
            "status": (
                "ok" if (present and found) or (not present and not found)
                else ("missing" if present and not found else "false_positive_risk")
            ),
        }

    required_types = [
        "role", "responsibility", "workflow", "process", "business_rule",
        "regulation", "form_or_record", "terminology",
    ]
    missing_types = [t for t in required_types if by_type.get(t, 0) == 0]
    if "workflow" in missing_types and by_type.get("process", 0) > 0:
        missing_types = [t for t in missing_types if t != "workflow"]
    if "process" in missing_types and by_type.get("workflow", 0) > 0:
        missing_types = [t for t in missing_types if t != "process"]

    return {
        "object_count": len(items),
        "types": dict(by_type),
        "labels_by_type": {k: v[:20] for k, v in labels_by_type.items()},
        "no_section_locations": no_section,
        "junk_terminology": junk,
        "duplicate_canonical": duplicates,
        "concept_evidence": evidence_hits,
        "missing_knowledge_types": missing_types,
    }


def main() -> int:
    docx_path = _find_docx(sys.argv)
    content = docx_path.read_bytes()
    filename = docx_path.name
    print(f"=== Parser: {filename} ===")
    parser = analyze_parser(content, filename)
    parser_failures = check_parser_invariants(parser)
    supported = source_supported_concepts(parser["full_text"])
    print(json.dumps({
        "warnings": parser["warnings"],
        "page_count": parser["page_count"],
        "block_kinds": parser["block_kinds"],
        "chunk_count": parser["chunk_count"],
        "semantic_chunk_count": parser["semantic_chunk_count"],
        "non_semantic_chunk_count": parser["non_semantic_chunk_count"],
        "non_semantic_kinds": parser["non_semantic_kinds"],
        "table_chunk_count": parser["table_chunk_count"],
        "list_block_count": parser["list_block_count"],
        "unique_heading_paths": parser["unique_heading_paths"],
        "heading_paths_sample": parser["heading_paths_sample"],
        "all_heading_paths": parser["all_heading_paths"],
        "parser_invariant_failures": parser_failures,
        "source_supported_concepts": supported,
    }, indent=2))

    settings = get_settings()
    print("\n=== LLM health ===")
    llm = get_llm_provider()
    llm_ok = bool(settings.ai_features_enabled and llm.health())
    print(f"ai_features_enabled={settings.ai_features_enabled}")
    print(f"provider={llm.name} chat={llm.chat_model} embed={llm.embedding_model}")
    print(f"reachable={llm_ok} base={settings.llm_base_url}")

    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    reg_db = settings.database_url.rsplit("/", 1)[1] + "_ckm_hr_regression"
    reg_url = settings.database_url.rsplit("/", 1)[0] + "/" + reg_db
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{reg_db}"'))
        conn.execute(text(f'CREATE DATABASE "{reg_db}"'))
    admin.dispose()

    engine = create_engine(reg_url, future=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    exit_code = 4

    try:
        with SessionLocal() as db:
            user = User(
                email=f"ckm-reg-{uuid.uuid4().hex[:8]}@example.com",
                hashed_password="unused",
                full_name="CKM Regression",
            )
            db.add(user)
            db.flush()
            company = Company(
                name=f"CKM HR Regression {uuid.uuid4().hex[:6]}",
                industry_key="pharma",
                location_key="vienna-at",
            )
            db.add(company)
            db.flush()
            db.add(CompanyRegulation(company_id=company.id, regulation_id="eu-gmp", position=0))
            db.add(UserCompanyAccess(user_id=user.id, company_id=company.id, role="admin"))
            db.flush()

            print("\n=== Ingest + embed ===")
            ingestion = IngestionService(db, llm if llm_ok else None)
            document = ingestion.ingest(
                company_id=company.id,
                filename=filename,
                content=content,
                uploaded_by=user.id,
                embed=llm_ok,
            )
            db.commit()

            chunks = list(db.scalars(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_order)
            ).all())
            semantic_rows = [c for c in chunks if c.is_semantic]
            embedded = [c for c in semantic_rows if c.embedding is not None]
            print(json.dumps({
                "document_id": str(document.id),
                "status": document.status,
                "warnings": document.warnings,
                "llm_reachable": llm_ok,
                "persisted_chunks": len(chunks),
                "semantic_chunks": len(semantic_rows),
                "embedded_semantic_chunks": len(embedded),
                "embeddings_complete": (
                    llm_ok and len(embedded) == len(semantic_rows) and len(semantic_rows) > 0
                ),
                "persisted_semantic_provenance_ok": all(bool(c.heading_path) for c in semantic_rows),
                "persisted_no_approval_in_semantic": not any(
                    any(b.get("type") == "approval_signature" for b in (c.extra.get("blocks") or []))
                    for c in semantic_rows
                ),
            }, indent=2))

            if document.status != DocumentStatus.PROCESSED:
                print("Ingestion did not reach PROCESSED.")
                return 3

            print("\n=== Deterministic CKM candidates (no LLM) ===")
            det = KnowledgeService._deterministic_candidates(semantic_rows, filename, "offline")
            det_no_section = [
                label for _kind, label, _p, _m, src in det if "(no section)" in src.location
            ]
            print(json.dumps({
                "deterministic_count": len(det),
                "by_type": dict(Counter(kind for kind, *_ in det)),
                "labels": [
                    {"type": kind, "label": label, "location": src.location}
                    for kind, label, _payload, _method, src in det
                ],
                "no_section_locations": det_no_section,
            }, indent=2))

            failures = list(parser_failures)
            if det_no_section:
                failures.append(f"deterministic Source (no section): {det_no_section}")

            ckm = None
            if llm_ok:
                print("\n=== CKM extract (LLM) ===")
                knowledge = KnowledgeService(db, CompanyService(db, CompanyRepository(db)))
                created, skipped = knowledge.extract_from_chunks(user.id, company.id, llm)
                db.commit()
                items = list(db.scalars(
                    select(KnowledgeObject).where(KnowledgeObject.company_id == company.id)
                ).all())
                ckm = analyze_knowledge(items, supported)
                print(json.dumps({"created": created, "skipped": skipped, **ckm}, indent=2, default=str))
                if len(embedded) != len(semantic_rows):
                    failures.append("embeddings incomplete for semantic chunks")
                if ckm["no_section_locations"]:
                    failures.append(f"Source (no section): {len(ckm['no_section_locations'])} objects")
                if ckm["junk_terminology"]:
                    failures.append(f"junk terminology: {ckm['junk_terminology']}")
                if ckm["duplicate_canonical"]:
                    failures.append(f"duplicate canonical objects: {ckm['duplicate_canonical']}")
            else:
                failures.append("LLM unreachable — embeddings and semantic CKM extract skipped")

            missing_concepts = []
            false_pos = []
            if ckm:
                missing_concepts = [
                    name for name, row in ckm["concept_evidence"].items()
                    if row["status"] == "missing"
                ]
                false_pos = [
                    name for name, row in ckm["concept_evidence"].items()
                    if row["status"] == "false_positive_risk"
                ]

            print("\n=== Summary ===")
            print(json.dumps({
                "parser_ok": not parser_failures,
                "llm_reachable": llm_ok,
                "embeddings_complete": (
                    llm_ok and len(embedded) == len(semantic_rows) and len(semantic_rows) > 0
                ),
                "missing_knowledge_types": (ckm or {}).get("missing_knowledge_types"),
                "missing_supported_concepts": missing_concepts,
                "false_positive_concepts": false_pos,
                "failures": failures,
                "pass": not failures and not missing_concepts,
            }, indent=2))
            exit_code = 0 if not failures and not missing_concepts else 4
    finally:
        engine.dispose()
        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{reg_db}' AND pid <> pg_backend_pid()"
            ))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{reg_db}"'))
        admin.dispose()

    return exit_code


if __name__ == "__main__":
    os.environ.setdefault("ENVIRONMENT", "local")
    raise SystemExit(main())
