from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.notifications.alert_governance import (
    AlertGovernanceEngine,
)
from platform_api.modules.notifications.feishu_card import FeishuBotClient
from platform_api.modules.notifications.repository import (
    SqlAlchemyNotificationsRepository,
)
from platform_api.modules.notifications.schemas import (
    AlertIncomingPayload,
    CreateChannelRequest,
    NotificationCategory,
    NotificationChannelItem,
    NotificationLevel,
    NotificationPage,
    NotificationStatus,
    TestChannelResponse,
    UnreadCountResponse,
    UpdateChannelRequest,
)
from platform_api.modules.notifications.service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
alerts_router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# 全局共享单例的防抖治理引擎与飞书客户端
_governance_engine = AlertGovernanceEngine(cooldown_seconds=300.0)
_feishu_client = FeishuBotClient()


def get_notification_service(request: Request) -> NotificationService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    # 在非 DB 请求时 fallback 纯 session
    return NotificationService(
        repository=None,  # 动态在请求内注入 session_scope
        governance_engine=_governance_engine,
        feishu_client=_feishu_client,
    )


# --- 外部告警网关路由 (Alerts Ingestion Gateway) ---


@alerts_router.post(
    "/incoming",
    status_code=status.HTTP_200_OK,
    summary="外部告警上报统一入口",
)
async def incoming_alert(
    payload: AlertIncomingPayload,
    request: Request,
    x_webhook_token: Annotated[
        str | None, Header(alias="X-Platform-Webhook-Token")
    ] = None,
) -> dict:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        dispatched, fingerprint, count = await service.process_incoming_alert(payload)

    return {
        "status": "success",
        "fingerprint": fingerprint,
        "dispatched": dispatched,
        "occurrence_count": count,
    }


@alerts_router.post(
    "/resolve",
    status_code=status.HTTP_200_OK,
    summary="告警恢复上报",
)
async def resolve_alert(
    source: str = Query(...),
    alert_type: str = Query(...),
    target_id: str = Query(...),
    request: Request = None,
) -> dict:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        resolved = await service.resolve_alert(source, alert_type, target_id)

    return {"status": "success", "resolved": resolved}


# --- 站内信 (In-App Notifications) 路由 ---


@router.get("", response_model=NotificationPage, summary="获取站内信列表")
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: NotificationStatus | None = Query(default=None),
    level: NotificationLevel | None = Query(default=None),
    category: NotificationCategory | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    request: Request = None,
    actor: ActorContext = Depends(get_actor_context),
) -> NotificationPage:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        recipient_id = uuid.UUID(actor.user_id) if actor.user_id else None
        return service.list_notifications(
            recipient_user_id=recipient_id,
            project_id=project_id,
            status=status,
            level=level,
            category=category,
            limit=limit,
            offset=offset,
        )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="获取当前用户未读消息数",
)
def get_unread_count(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> UnreadCountResponse:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        recipient_id = uuid.UUID(actor.user_id) if actor.user_id else None
        count = service.get_unread_count(recipient_id)
        return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", summary="标记单条站内信已读")
def mark_as_read(
    notification_id: uuid.UUID,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> dict:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        recipient_id = uuid.UUID(actor.user_id) if actor.user_id else None
        success = service.mark_as_read(notification_id, recipient_id)
        if not success:
            raise HTTPException(status_code=404, detail="通知未找到或无权操作")
        return {"status": "success", "id": str(notification_id)}


@router.post("/mark-all-read", summary="一键全部已读")
def mark_all_read(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> dict:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        recipient_id = uuid.UUID(actor.user_id) if actor.user_id else None
        count = service.mark_all_read(recipient_id)
        return {"status": "success", "updated_count": count}


# --- 通知渠道 (Notification Channels) 管理路由 ---


@router.get(
    "/channels",
    response_model=list[NotificationChannelItem],
    summary="查询配置的通知渠道列表",
)
def list_channels(
    project_id: uuid.UUID | None = Query(default=None),
    enabled_only: bool = Query(default=False),
    request: Request = None,
    actor: ActorContext = Depends(get_actor_context),
) -> list[NotificationChannelItem]:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        records = service.list_channels(
            project_id=project_id, enabled_only=enabled_only
        )
        return [
            NotificationChannelItem(
                id=r.id,
                name=r.name,
                project_ids=r.project_ids or [],
                channel_type=r.channel_type,
                endpoint_url=r.endpoint_url,
                secret_token=r.secret_token,
                is_enabled=r.is_enabled,
                subscribed_events=r.subscribed_events or [],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]


@router.post(
    "/channels",
    response_model=NotificationChannelItem,
    status_code=status.HTTP_201_CREATED,
    summary="新增通知渠道",
)
def create_channel(
    req: CreateChannelRequest,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> NotificationChannelItem:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        r = service.create_channel(req)
        return NotificationChannelItem(
            id=r.id,
            name=r.name,
            project_ids=r.project_ids or [],
            channel_type=r.channel_type,
            endpoint_url=r.endpoint_url,
            secret_token=r.secret_token,
            is_enabled=r.is_enabled,
            subscribed_events=r.subscribed_events or [],
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


@router.patch(
    "/channels/{channel_id}",
    response_model=NotificationChannelItem,
    summary="更新通知渠道",
)
def update_channel(
    channel_id: uuid.UUID,
    req: UpdateChannelRequest,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> NotificationChannelItem:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        r = service.update_channel(channel_id, req)
        if not r:
            raise HTTPException(status_code=404, detail="渠道不存在")
        return NotificationChannelItem(
            id=r.id,
            name=r.name,
            project_ids=r.project_ids or [],
            channel_type=r.channel_type,
            endpoint_url=r.endpoint_url,
            secret_token=r.secret_token,
            is_enabled=r.is_enabled,
            subscribed_events=r.subscribed_events or [],
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


@router.delete("/channels/{channel_id}", summary="删除通知渠道")
def delete_channel(
    channel_id: uuid.UUID,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> dict:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        success = service.delete_channel(channel_id)
        if not success:
            raise HTTPException(status_code=404, detail="渠道不存在")
        return {"status": "success", "id": str(channel_id)}


@router.post(
    "/channels/{channel_id}/test",
    response_model=TestChannelResponse,
    summary="即时测试渠道连通性",
)
async def test_channel(
    channel_id: uuid.UUID,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> TestChannelResponse:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    with session_scope(session_factory) as session:
        repo = SqlAlchemyNotificationsRepository(session)
        service = NotificationService(
            repository=repo,
            governance_engine=_governance_engine,
            feishu_client=_feishu_client,
        )
        return await service.test_channel(channel_id)
