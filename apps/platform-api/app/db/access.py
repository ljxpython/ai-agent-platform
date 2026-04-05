from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.models import (
    Announcement,
    AnnouncementRead,
    Agent,
    AssistantProfile,
    AuditLog,
    Project,
    ProjectGraphPolicy,
    ProjectMember,
    ProjectModelPolicy,
    ProjectToolPolicy,
    RefreshToken,
    RuntimeCatalogGraph,
    RuntimeCatalogModel,
    RuntimeCatalogTool,
    Tenant,
    User,
)
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def get_user_by_username(session: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return session.scalar(stmt)


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def create_user_account(
    session: Session,
    username: str,
    password_hash: str,
    *,
    is_super_admin: bool = False,
) -> User:
    user = User(
        username=username,
        password_hash=password_hash,
        status="active",
        is_super_admin=is_super_admin,
        external_subject=username,
        email=None,
    )
    session.add(user)
    session.flush()
    return user


def update_user_password_hash(session: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    session.flush()


def count_users(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(User)) or 0)


def count_super_admins(session: Session) -> int:
    stmt = (
        select(func.count())
        .select_from(User)
        .where(User.is_super_admin.is_(True), User.status == "active")
    )
    return int(session.scalar(stmt) or 0)


def list_users(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    *,
    query: str | None = None,
    status: str | None = None,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[User], int]:
    base_stmt = select(User)
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(func.lower(User.username).like(normalized_query))
    if isinstance(status, str) and status.strip():
        base_stmt = base_stmt.where(User.status == status.strip())
    if exclude_user_ids:
        base_stmt = base_stmt.where(User.id.notin_(exclude_user_ids))

    stmt = base_stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def create_refresh_token(
    session: Session,
    user_id: uuid.UUID,
    token_id: str,
    ttl_seconds: int,
) -> RefreshToken:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    row = RefreshToken(user_id=user_id, token_id=token_id, expires_at=expires_at)
    session.add(row)
    session.flush()
    return row


def get_refresh_token(session: Session, token_id: str) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_id == token_id)
    return session.scalar(stmt)


def revoke_refresh_token(session: Session, token_id: str) -> None:
    row = get_refresh_token(session, token_id)
    if row is None:
        return
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
    session.flush()


def revoke_all_refresh_tokens_for_user(session: Session, user_id: uuid.UUID) -> None:
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    now = datetime.now(timezone.utc)
    for row in session.scalars(stmt).all():
        row.revoked_at = now
    session.flush()


def get_or_create_default_tenant(session: Session) -> Tenant:
    stmt = select(Tenant).where(Tenant.slug == "__default")
    tenant = session.scalar(stmt)
    if tenant is not None:
        return tenant
    tenant = Tenant(name="Default", slug="__default", status="active")
    session.add(tenant)
    session.flush()
    return tenant


def create_project(
    session: Session,
    tenant_id: uuid.UUID,
    name: str,
    *,
    description: str | None = None,
) -> Project:
    project = Project(
        tenant_id=tenant_id,
        name=name,
        code=None,
        description=(description or "").strip(),
    )
    session.add(project)
    session.flush()
    return project


def list_active_projects(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    *,
    query: str | None = None,
) -> tuple[list[Project], int]:
    base_stmt = select(Project).where(Project.status != "deleted")
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(
            func.lower(Project.name).like(normalized_query)
            | func.lower(Project.description).like(normalized_query)
        )
    stmt = base_stmt.order_by(desc(Project.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def list_active_projects_for_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
) -> tuple[list[Project], int]:
    base_stmt = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            ProjectMember.user_id == user_id,
            Project.status != "deleted",
        )
    )
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(
            func.lower(Project.name).like(normalized_query)
            | func.lower(Project.description).like(normalized_query)
        )
    stmt = base_stmt.order_by(desc(Project.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_project_member(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember | None:
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    )
    return session.scalar(stmt)


def list_project_members(
    session: Session, project_id: uuid.UUID
) -> list[ProjectMember]:
    stmt = (
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(asc(ProjectMember.created_at))
    )
    return list(session.scalars(stmt).all())


def list_visible_announcements(
    session: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> list[tuple[Announcement, bool]]:
    current_time = now or datetime.now(timezone.utc)
    visibility_clause = (
        Announcement.scope_type == "global"
        if project_id is None
        else (
            (Announcement.scope_type == "global")
            | (
                (Announcement.scope_type == "project")
                & (Announcement.scope_project_id == project_id)
            )
        )
    )
    stmt = (
        select(Announcement)
        .where(
            Announcement.status == "published",
            Announcement.publish_at <= current_time,
            (Announcement.expire_at.is_(None) | (Announcement.expire_at >= current_time)),
            visibility_clause,
        )
        .order_by(desc(Announcement.publish_at), desc(Announcement.created_at))
    )
    announcements = list(session.scalars(stmt).all())
    if not announcements:
        return []

    announcement_ids = [item.id for item in announcements]
    read_stmt = select(AnnouncementRead.announcement_id).where(
        AnnouncementRead.user_id == user_id,
        AnnouncementRead.announcement_id.in_(announcement_ids),
    )
    read_ids = set(session.scalars(read_stmt).all())
    return [(item, item.id in read_ids) for item in announcements]


def list_announcements_admin(
    session: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
    status: str | None = None,
    scope_type: str | None = None,
    scope_project_id: uuid.UUID | None = None,
) -> tuple[list[Announcement], int]:
    base_stmt = select(Announcement)
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(
            func.lower(Announcement.title).like(normalized_query)
            | func.lower(Announcement.summary).like(normalized_query)
            | func.lower(Announcement.body).like(normalized_query)
        )
    if isinstance(status, str) and status.strip():
        base_stmt = base_stmt.where(Announcement.status == status.strip())
    if isinstance(scope_type, str) and scope_type.strip():
        base_stmt = base_stmt.where(Announcement.scope_type == scope_type.strip())
    if scope_project_id is not None:
        base_stmt = base_stmt.where(Announcement.scope_project_id == scope_project_id)

    stmt = base_stmt.order_by(desc(Announcement.publish_at), desc(Announcement.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_announcement_by_id(
    session: Session, announcement_id: uuid.UUID
) -> Announcement | None:
    return session.get(Announcement, announcement_id)


def create_announcement(
    session: Session,
    *,
    title: str,
    summary: str,
    body: str,
    tone: str,
    scope_type: str,
    scope_project_id: uuid.UUID | None,
    status: str,
    publish_at: datetime,
    expire_at: datetime | None,
    created_by: uuid.UUID | None,
    updated_by: uuid.UUID | None,
) -> Announcement:
    row = Announcement(
        title=title,
        summary=summary,
        body=body,
        tone=tone,
        scope_type=scope_type,
        scope_project_id=scope_project_id,
        status=status,
        publish_at=publish_at,
        expire_at=expire_at,
        created_by=created_by,
        updated_by=updated_by,
    )
    session.add(row)
    session.flush()
    return row


def update_announcement(
    session: Session,
    row: Announcement,
    *,
    title: str,
    summary: str,
    body: str,
    tone: str,
    scope_type: str,
    scope_project_id: uuid.UUID | None,
    status: str,
    publish_at: datetime,
    expire_at: datetime | None,
    updated_by: uuid.UUID | None,
) -> Announcement:
    row.title = title
    row.summary = summary
    row.body = body
    row.tone = tone
    row.scope_type = scope_type
    row.scope_project_id = scope_project_id
    row.status = status
    row.publish_at = publish_at
    row.expire_at = expire_at
    row.updated_by = updated_by
    session.flush()
    return row


def delete_announcement(session: Session, row: Announcement) -> None:
    session.delete(row)
    session.flush()


def get_announcement_read(
    session: Session, *, announcement_id: uuid.UUID, user_id: uuid.UUID
) -> AnnouncementRead | None:
    stmt = select(AnnouncementRead).where(
        AnnouncementRead.announcement_id == announcement_id,
        AnnouncementRead.user_id == user_id,
    )
    return session.scalar(stmt)


def mark_announcement_read(
    session: Session, *, announcement_id: uuid.UUID, user_id: uuid.UUID
) -> AnnouncementRead:
    row = get_announcement_read(
        session, announcement_id=announcement_id, user_id=user_id
    )
    if row is None:
        row = AnnouncementRead(announcement_id=announcement_id, user_id=user_id)
        session.add(row)
        session.flush()
        return row

    row.read_at = datetime.now(timezone.utc)
    session.flush()
    return row


def mark_all_announcements_read(
    session: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> int:
    visible_items = list_visible_announcements(
        session, user_id=user_id, project_id=project_id, now=now
    )
    changed = 0
    for announcement, is_read in visible_items:
        if is_read:
            continue
        mark_announcement_read(
            session, announcement_id=announcement.id, user_id=user_id
        )
        changed += 1
    return changed


def list_user_project_memberships(
    session: Session, user_id: uuid.UUID
) -> list[tuple[ProjectMember, Project]]:
    stmt = (
        select(ProjectMember, Project)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == user_id,
            Project.status != "deleted",
        )
        .order_by(desc(Project.created_at))
    )
    return list(session.execute(stmt).tuples().all())


def count_project_admins(session: Session, project_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(ProjectMember)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == "admin",
        )
    )
    return int(session.scalar(stmt) or 0)


def upsert_project_member(
    session: Session, project_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> ProjectMember:
    existing = get_project_member(session, project_id, user_id)
    if existing is None:
        existing = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        session.add(existing)
        session.flush()
        return existing
    existing.role = role
    session.flush()
    return existing


def remove_project_member(session: Session, member: ProjectMember) -> None:
    session.delete(member)
    session.flush()


def get_agent_by_project_and_langgraph_assistant_id(
    session: Session,
    project_id: uuid.UUID,
    langgraph_assistant_id: str,
) -> Agent | None:
    stmt = select(Agent).where(
        Agent.project_id == project_id,
        Agent.langgraph_assistant_id == langgraph_assistant_id,
    )
    return session.scalar(stmt)


def get_agent_by_id(session: Session, agent_id: uuid.UUID) -> Agent | None:
    return session.get(Agent, agent_id)


def create_agent(
    session: Session,
    *,
    project_id: uuid.UUID,
    name: str,
    graph_id: str,
    runtime_base_url: str,
    langgraph_assistant_id: str,
    description: str,
) -> Agent:
    row = Agent(
        project_id=project_id,
        name=name,
        graph_id=graph_id,
        runtime_base_url=runtime_base_url,
        langgraph_assistant_id=langgraph_assistant_id,
        description=description,
        sync_status="ready",
        last_sync_error=None,
        last_synced_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


def get_assistant_profile_by_agent_id(
    session: Session, agent_id: uuid.UUID
) -> AssistantProfile | None:
    stmt = select(AssistantProfile).where(AssistantProfile.agent_id == agent_id)
    return session.scalar(stmt)


def upsert_assistant_profile(
    session: Session,
    *,
    agent_id: uuid.UUID,
    status: str,
    config: dict[str, Any],
    context: dict[str, Any],
    metadata_json: dict[str, Any],
    actor_user_id: uuid.UUID,
) -> AssistantProfile:
    row = get_assistant_profile_by_agent_id(session, agent_id)
    if row is None:
        row = AssistantProfile(
            agent_id=agent_id,
            status=status,
            config=config,
            context=context,
            metadata_json=metadata_json,
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        session.add(row)
        session.flush()
        return row

    row.status = status
    row.config = config
    row.context = context
    row.metadata_json = metadata_json
    row.updated_by = actor_user_id
    session.flush()
    return row


def list_project_agents(
    session: Session,
    *,
    project_id: uuid.UUID,
    limit: int,
    offset: int,
    query: str | None = None,
    graph_id: str | None = None,
) -> tuple[list[Agent], int]:
    base_stmt = select(Agent).where(Agent.project_id == project_id)
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(
            func.lower(Agent.name).like(normalized_query)
            | func.lower(Agent.description).like(normalized_query)
            | func.lower(Agent.graph_id).like(normalized_query)
            | func.lower(Agent.langgraph_assistant_id).like(normalized_query)
        )
    if isinstance(graph_id, str) and graph_id.strip():
        base_stmt = base_stmt.where(Agent.graph_id == graph_id.strip())

    stmt = base_stmt.order_by(desc(Agent.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def delete_agent(session: Session, row: Agent) -> None:
    session.delete(row)
    session.flush()


def update_agent_sync_state(
    session: Session,
    row: Agent,
    *,
    sync_status: str,
    last_sync_error: str | None,
    last_synced_at: datetime | None,
) -> Agent:
    row.sync_status = sync_status
    row.last_sync_error = last_sync_error
    row.last_synced_at = last_synced_at
    session.flush()
    return row


def update_agent_runtime_fields(
    session: Session,
    row: Agent,
    *,
    graph_id: str,
    name: str,
    description: str,
    runtime_base_url: str,
) -> Agent:
    row.graph_id = graph_id
    row.name = name
    row.description = description
    row.runtime_base_url = runtime_base_url
    session.flush()
    return row


def get_runtime_catalog_model_by_key(
    session: Session, runtime_id: str, model_key: str
) -> RuntimeCatalogModel | None:
    stmt = select(RuntimeCatalogModel).where(
        RuntimeCatalogModel.runtime_id == runtime_id,
        RuntimeCatalogModel.model_key == model_key,
    )
    return session.scalar(stmt)


def get_runtime_catalog_tool_by_key(
    session: Session, runtime_id: str, tool_key: str
) -> RuntimeCatalogTool | None:
    stmt = select(RuntimeCatalogTool).where(
        RuntimeCatalogTool.runtime_id == runtime_id,
        RuntimeCatalogTool.tool_key == tool_key,
    )
    return session.scalar(stmt)


def get_runtime_catalog_graph_by_key(
    session: Session, runtime_id: str, graph_key: str
) -> RuntimeCatalogGraph | None:
    stmt = select(RuntimeCatalogGraph).where(
        RuntimeCatalogGraph.runtime_id == runtime_id,
        RuntimeCatalogGraph.graph_key == graph_key,
    )
    return session.scalar(stmt)


def upsert_runtime_model_catalog_items(
    session: Session,
    *,
    runtime_id: str,
    items: list[dict[str, Any]],
    synced_at: datetime,
) -> list[RuntimeCatalogModel]:
    rows: list[RuntimeCatalogModel] = []
    for item in items:
        model_key = str(item.get("model_id") or "").strip()
        if not model_key:
            continue
        row = get_runtime_catalog_model_by_key(session, runtime_id, model_key)
        if row is None:
            row = RuntimeCatalogModel(runtime_id=runtime_id, model_key=model_key)
            session.add(row)
        row.display_name = str(item.get("display_name") or model_key)
        row.is_default_runtime = bool(item.get("is_default"))
        row.raw_payload_json = dict(item)
        row.sync_status = "ready"
        row.last_seen_at = synced_at
        row.last_synced_at = synced_at
        row.is_deleted = False
        rows.append(row)
    session.flush()
    return rows


def upsert_runtime_tool_catalog_items(
    session: Session,
    *,
    runtime_id: str,
    items: list[dict[str, Any]],
    synced_at: datetime,
) -> list[RuntimeCatalogTool]:
    rows: list[RuntimeCatalogTool] = []
    for item in items:
        name = str(item.get("name") or "").strip()
        source = str(item.get("source") or "").strip()
        if not name:
            continue
        tool_key = f"{source}:{name}" if source else name
        row = get_runtime_catalog_tool_by_key(session, runtime_id, tool_key)
        if row is None:
            row = RuntimeCatalogTool(
                runtime_id=runtime_id, tool_key=tool_key, name=name
            )
            session.add(row)
        row.name = name
        row.source = source or None
        row.description = str(item.get("description") or "") or None
        row.raw_payload_json = dict(item)
        row.sync_status = "ready"
        row.last_seen_at = synced_at
        row.last_synced_at = synced_at
        row.is_deleted = False
        rows.append(row)
    session.flush()
    return rows


def upsert_runtime_graph_catalog_items(
    session: Session,
    *,
    runtime_id: str,
    items: list[dict[str, Any]],
    synced_at: datetime,
    source_type: str,
) -> list[RuntimeCatalogGraph]:
    rows: list[RuntimeCatalogGraph] = []
    for item in items:
        graph_key = str(item.get("graph_id") or item.get("graph_key") or "").strip()
        if not graph_key:
            continue
        row = get_runtime_catalog_graph_by_key(session, runtime_id, graph_key)
        if row is None:
            row = RuntimeCatalogGraph(runtime_id=runtime_id, graph_key=graph_key)
            session.add(row)
        row.display_name = str(item.get("display_name") or graph_key) or graph_key
        row.description = str(item.get("description") or "") or None
        row.source_type = source_type
        row.raw_payload_json = dict(item)
        row.sync_status = "ready"
        row.last_seen_at = synced_at
        row.last_synced_at = synced_at
        row.is_deleted = False
        rows.append(row)
    session.flush()
    return rows


def mark_missing_runtime_catalog_models_deleted(
    session: Session, *, runtime_id: str, active_keys: set[str], synced_at: datetime
) -> None:
    stmt = select(RuntimeCatalogModel).where(
        RuntimeCatalogModel.runtime_id == runtime_id
    )
    for row in session.scalars(stmt).all():
        if row.model_key not in active_keys:
            row.is_deleted = True
            row.last_synced_at = synced_at
    session.flush()


def mark_missing_runtime_catalog_tools_deleted(
    session: Session, *, runtime_id: str, active_keys: set[str], synced_at: datetime
) -> None:
    stmt = select(RuntimeCatalogTool).where(RuntimeCatalogTool.runtime_id == runtime_id)
    for row in session.scalars(stmt).all():
        if row.tool_key not in active_keys:
            row.is_deleted = True
            row.last_synced_at = synced_at
    session.flush()


def mark_missing_runtime_catalog_graphs_deleted(
    session: Session, *, runtime_id: str, active_keys: set[str], synced_at: datetime
) -> None:
    stmt = select(RuntimeCatalogGraph).where(
        RuntimeCatalogGraph.runtime_id == runtime_id
    )
    for row in session.scalars(stmt).all():
        if row.graph_key not in active_keys:
            row.is_deleted = True
            row.last_synced_at = synced_at
    session.flush()


def list_runtime_model_catalog_items(
    session: Session, *, runtime_id: str, include_deleted: bool = False
) -> list[RuntimeCatalogModel]:
    stmt = select(RuntimeCatalogModel).where(
        RuntimeCatalogModel.runtime_id == runtime_id
    )
    if not include_deleted:
        stmt = stmt.where(RuntimeCatalogModel.is_deleted.is_(False))
    stmt = stmt.order_by(
        desc(RuntimeCatalogModel.is_default_runtime), asc(RuntimeCatalogModel.model_key)
    )
    return list(session.scalars(stmt).all())


def list_runtime_tool_catalog_items(
    session: Session, *, runtime_id: str, include_deleted: bool = False
) -> list[RuntimeCatalogTool]:
    stmt = select(RuntimeCatalogTool).where(RuntimeCatalogTool.runtime_id == runtime_id)
    if not include_deleted:
        stmt = stmt.where(RuntimeCatalogTool.is_deleted.is_(False))
    stmt = stmt.order_by(asc(RuntimeCatalogTool.source), asc(RuntimeCatalogTool.name))
    return list(session.scalars(stmt).all())


def list_runtime_graph_catalog_items(
    session: Session, *, runtime_id: str, include_deleted: bool = False
) -> list[RuntimeCatalogGraph]:
    stmt = select(RuntimeCatalogGraph).where(
        RuntimeCatalogGraph.runtime_id == runtime_id
    )
    if not include_deleted:
        stmt = stmt.where(RuntimeCatalogGraph.is_deleted.is_(False))
    stmt = stmt.order_by(asc(RuntimeCatalogGraph.graph_key))
    return list(session.scalars(stmt).all())


def upsert_project_graph_policy(
    session: Session,
    *,
    project_id: uuid.UUID,
    graph_catalog_id: uuid.UUID,
    is_enabled: bool,
    display_order: int | None,
    note: str | None,
    updated_by: uuid.UUID | None,
) -> ProjectGraphPolicy:
    stmt = select(ProjectGraphPolicy).where(
        ProjectGraphPolicy.project_id == project_id,
        ProjectGraphPolicy.graph_catalog_id == graph_catalog_id,
    )
    row = session.scalar(stmt)
    if row is None:
        row = ProjectGraphPolicy(
            project_id=project_id, graph_catalog_id=graph_catalog_id
        )
        session.add(row)
    row.is_enabled = is_enabled
    row.display_order = display_order
    row.note = note
    row.updated_by = updated_by
    session.flush()
    return row


def upsert_project_model_policy(
    session: Session,
    *,
    project_id: uuid.UUID,
    model_catalog_id: uuid.UUID,
    is_enabled: bool,
    is_default_for_project: bool,
    temperature_default: Any,
    note: str | None,
    updated_by: uuid.UUID | None,
) -> ProjectModelPolicy:
    stmt = select(ProjectModelPolicy).where(
        ProjectModelPolicy.project_id == project_id,
        ProjectModelPolicy.model_catalog_id == model_catalog_id,
    )
    row = session.scalar(stmt)
    if row is None:
        row = ProjectModelPolicy(
            project_id=project_id, model_catalog_id=model_catalog_id
        )
        session.add(row)
    row.is_enabled = is_enabled
    row.is_default_for_project = is_default_for_project
    row.temperature_default = temperature_default
    row.note = note
    row.updated_by = updated_by
    session.flush()
    return row


def upsert_project_tool_policy(
    session: Session,
    *,
    project_id: uuid.UUID,
    tool_catalog_id: uuid.UUID,
    is_enabled: bool,
    display_order: int | None,
    note: str | None,
    updated_by: uuid.UUID | None,
) -> ProjectToolPolicy:
    stmt = select(ProjectToolPolicy).where(
        ProjectToolPolicy.project_id == project_id,
        ProjectToolPolicy.tool_catalog_id == tool_catalog_id,
    )
    row = session.scalar(stmt)
    if row is None:
        row = ProjectToolPolicy(project_id=project_id, tool_catalog_id=tool_catalog_id)
        session.add(row)
    row.is_enabled = is_enabled
    row.display_order = display_order
    row.note = note
    row.updated_by = updated_by
    session.flush()
    return row


def list_project_graph_policies(
    session: Session, *, project_id: uuid.UUID
) -> list[ProjectGraphPolicy]:
    stmt = (
        select(ProjectGraphPolicy)
        .where(ProjectGraphPolicy.project_id == project_id)
        .order_by(
            asc(ProjectGraphPolicy.display_order), asc(ProjectGraphPolicy.updated_at)
        )
    )
    return list(session.scalars(stmt).all())


def list_project_model_policies(
    session: Session, *, project_id: uuid.UUID
) -> list[ProjectModelPolicy]:
    stmt = (
        select(ProjectModelPolicy)
        .where(ProjectModelPolicy.project_id == project_id)
        .order_by(
            desc(ProjectModelPolicy.is_default_for_project),
            asc(ProjectModelPolicy.updated_at),
        )
    )
    return list(session.scalars(stmt).all())


def list_project_tool_policies(
    session: Session, *, project_id: uuid.UUID
) -> list[ProjectToolPolicy]:
    stmt = (
        select(ProjectToolPolicy)
        .where(ProjectToolPolicy.project_id == project_id)
        .order_by(
            asc(ProjectToolPolicy.display_order), asc(ProjectToolPolicy.updated_at)
        )
    )
    return list(session.scalars(stmt).all())


def create_audit_log(
    session: Session,
    request_id: str,
    plane: str,
    method: str,
    path: str,
    query: str,
    status_code: int,
    duration_ms: int,
    project_id: uuid.UUID | None,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    user_subject: str | None,
    client_ip: str | None,
    user_agent: str | None,
    response_size: int | None,
    metadata_json: dict | None,
) -> AuditLog:
    log = AuditLog(
        request_id=request_id,
        plane=plane,
        method=method,
        path=path,
        query=query,
        status_code=status_code,
        duration_ms=duration_ms,
        project_id=project_id,
        tenant_id=tenant_id,
        user_id=user_id,
        user_subject=user_subject,
        client_ip=client_ip,
        user_agent=user_agent,
        response_size=response_size,
        metadata_json=metadata_json,
    )
    session.add(log)
    session.flush()
    return log


def list_audit_logs_for_project(
    session: Session,
    project_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    base_stmt = select(AuditLog).where(AuditLog.project_id == project_id)
    stmt = base_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def list_audit_logs(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    base_stmt = select(AuditLog)
    stmt = base_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total
