from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.knowledge import LightRagKnowledgeClient
from app.core.config import Settings
from app.modules.project_knowledge.application.service import ProjectKnowledgeService


def build_project_knowledge_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
    forwarded_headers: Mapping[str, str] | None = None,
) -> ProjectKnowledgeService:
    upstream = LightRagKnowledgeClient(
        base_url=settings.knowledge_upstream_url,
        api_key=settings.knowledge_upstream_api_key,
        timeout_seconds=settings.knowledge_upstream_timeout_seconds,
        forwarded_headers=forwarded_headers,
    )
    return ProjectKnowledgeService(
        session_factory=session_factory,
        upstream=upstream,
        service_base_url=settings.knowledge_upstream_url,
    )
