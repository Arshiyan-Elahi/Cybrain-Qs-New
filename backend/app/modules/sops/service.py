import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger, log_event
from app.modules.companies.service import CompanyService
from app.modules.knowledge.generation_context import GenerationContextService
from app.modules.sops.blueprint import build_blueprint, embed_texts
from app.modules.sops.models import SopProject
from app.modules.sops.repository import SopProjectRepository
from app.modules.sops.schemas import SopBlueprintRead, SopProjectCreate
from app.shared.enums import SopProjectStatus

logger = get_logger("app.sops")

BLUEPRINT_KNOWLEDGE_LIMIT = 50
BLUEPRINT_CHUNK_LIMIT = 12


class SopProjectService:
    def __init__(
        self,
        db: Session,
        companies: CompanyService,
        repo: SopProjectRepository,
        context: GenerationContextService,
        llm,
    ) -> None:
        self.db = db
        self.companies = companies
        self.repo = repo
        self.context = context
        self.llm = llm

    def create(self, user_id: uuid.UUID, company_id: uuid.UUID, payload: SopProjectCreate) -> SopProject:
        company = self.companies.get(user_id, company_id)
        project = SopProject(
            company_id=company.id,
            title=payload.title.strip(),
            topic=payload.topic.strip(),
            status=SopProjectStatus.PLANNING,
            created_by=user_id,
            blueprint_version=0,
            blueprint=None,
            context_option_ids=list(payload.context_option_ids),
            additional_context=payload.additional_context.strip(),
        )
        self.repo.add(project)
        log_event(
            logger,
            "sop_project_created",
            "SOP project created",
            company_id=str(company.id),
            project_id=str(project.id),
        )
        return project

    def get(self, user_id: uuid.UUID, company_id: uuid.UUID, project_id: uuid.UUID) -> SopProject:
        self.companies.get(user_id, company_id)
        project = self.repo.get_for_company(company_id, project_id)
        if project is None:
            raise NotFoundError("SOP project not found.")
        return project

    def build_blueprint(
        self, user_id: uuid.UUID, company_id: uuid.UUID, project_id: uuid.UUID
    ) -> SopProject:
        project = self.get(user_id, company_id, project_id)
        query = project.topic or project.title
        package = self.context.build(
            user_id,
            company_id,
            query,
            knowledge_limit=BLUEPRINT_KNOWLEDGE_LIMIT,
            chunk_limit=BLUEPRINT_CHUNK_LIMIT,
        )
        trusted = self.context.trusted_knowledge(user_id, company_id)
        section_texts = [query, project.title]
        # Embeddings only rank existing items; they never create facts.
        embed_pairs = embed_texts(self.llm, section_texts)
        raw = build_blueprint(
            db=self.db,
            company_id=project.company_id,
            title=project.title,
            topic=project.topic,
            package=package,
            trusted=trusted,
            embed_pairs=embed_pairs,
        )
        blueprint = SopBlueprintRead.model_validate(raw)
        if _contains_generated_prose(blueprint):
            raise ValidationError("Blueprint mapping produced unexpected generated prose.")
        project.blueprint = blueprint.model_dump(mode="json", by_alias=True)
        project.blueprint_version = int(project.blueprint_version) + 1
        project.status = SopProjectStatus.BLUEPRINT_READY
        self.db.flush()
        log_event(
            logger,
            "sop_blueprint_built",
            "SOP blueprint assembled",
            company_id=str(project.company_id),
            project_id=str(project.id),
            blueprint_version=project.blueprint_version,
            structure_source=blueprint.structure_source,
            grounded=blueprint.summary.grounded,
            partial=blueprint.summary.partial,
            blocked=blueprint.summary.blocked,
        )
        return project

    def mark_generation_ready(
        self, user_id: uuid.UUID, company_id: uuid.UUID, project_id: uuid.UUID
    ) -> SopProject:
        project = self.get(user_id, company_id, project_id)
        if project.blueprint is None or project.blueprint_version < 1:
            raise ValidationError("Build a blueprint before marking the project generation-ready.")
        project.status = SopProjectStatus.GENERATION_READY
        self.db.flush()
        return project


def _contains_generated_prose(blueprint: SopBlueprintRead) -> bool:
    """Reject accidental SOP-body generation. Objectives are short mapping notes."""
    for section in blueprint.sections:
        if len(section.objective) > 1200:
            return True
        if "shall " in section.objective.casefold() and len(section.objective) > 400:
            return True
    return False
