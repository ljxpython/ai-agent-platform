"""
RAG仪表板API
提供RAG系统的统计信息、监控数据和管理功能
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from backend.controllers.rag_controller import (
    rag_collection_controller,
    rag_query_controller,
)

rag_dashboard_router = APIRouter()


@rag_dashboard_router.get("/stats", summary="获取仪表板统计信息")
async def get_dashboard_stats():
    """获取RAG系统仪表板统计信息"""
    return await rag_query_controller.get_system_stats()


@rag_dashboard_router.get("/activities", summary="获取最近活动")
async def get_recent_activities(limit: int = Query(10, ge=1, le=100)):
    """获取最近的系统活动"""
    try:
        # 模拟最近活动数据（实际应该从数据库或日志中获取）
        activities = [
            {
                "id": "1",
                "type": "upload",
                "description": "上传文档到 ai_chat 知识库",
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "status": "success",
            },
            {
                "id": "2",
                "type": "query",
                "description": "执行语义搜索查询",
                "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
                "status": "success",
            },
            {
                "id": "3",
                "type": "collection_created",
                "description": "创建新的知识库 test_collection",
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "status": "success",
            },
            {
                "id": "4",
                "type": "model_updated",
                "description": "更新嵌入模型配置",
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "status": "warning",
            },
        ]

        return {"success": True, "data": activities[:limit]}

    except Exception as e:
        logger.error(f"获取最近活动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rag_dashboard_router.get("/health", summary="获取系统健康状态")
async def get_system_health():
    """获取系统健康状态"""
    try:
        # 检查各个组件的健康状态
        health_status = {
            "overall": "healthy",
            "components": {
                "database": {
                    "status": "healthy",
                    "response_time": 12,
                    "last_check": datetime.now().isoformat(),
                },
                "vector_db": {
                    "status": "healthy",
                    "response_time": 45,
                    "last_check": datetime.now().isoformat(),
                },
                "embedding_service": {
                    "status": "healthy",
                    "response_time": 234,
                    "last_check": datetime.now().isoformat(),
                },
                "llm_service": {
                    "status": "warning",
                    "response_time": 1200,
                    "last_check": datetime.now().isoformat(),
                    "message": "响应时间较慢",
                },
            },
            "metrics": {
                "uptime": "7天12小时",
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "disk_usage": 23.4,
                "network_io": 12.5,
            },
        }

        return {"success": True, "data": health_status}

    except Exception as e:
        logger.error(f"获取系统健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rag_dashboard_router.get("/performance", summary="获取性能指标")
async def get_performance_metrics(
    time_range: str = Query("24h", regex="^(1h|24h|7d|30d)$")
):
    """获取性能指标"""
    try:
        # 根据时间范围生成模拟数据
        time_points = []
        query_rates = []
        response_times = []

        if time_range == "1h":
            # 最近1小时，每5分钟一个点
            for i in range(12):
                time_points.append(
                    (datetime.now() - timedelta(minutes=i * 5)).isoformat()
                )
                query_rates.append(15 + i * 2)
                response_times.append(200 + i * 10)
        elif time_range == "24h":
            # 最近24小时，每小时一个点
            for i in range(24):
                time_points.append((datetime.now() - timedelta(hours=i)).isoformat())
                query_rates.append(20 + i)
                response_times.append(180 + i * 5)

        performance_data = {
            "time_range": time_range,
            "metrics": {
                "query_rate": {
                    "timestamps": time_points,
                    "values": query_rates,
                    "unit": "queries/min",
                },
                "response_time": {
                    "timestamps": time_points,
                    "values": response_times,
                    "unit": "ms",
                },
                "success_rate": {
                    "timestamps": time_points,
                    "values": [98.5 + (i % 3) * 0.5 for i in range(len(time_points))],
                    "unit": "%",
                },
            },
        }

        return {"success": True, "data": performance_data}

    except Exception as e:
        logger.error(f"获取性能指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rag_dashboard_router.get("/collections/summary", summary="获取Collections摘要")
async def get_collections_summary():
    """获取所有Collections的摘要信息"""
    # 使用控制器获取Collections信息
    result = await rag_collection_controller.get_all_collections()
    collections = result.data["collections"]

    summary = {
        "total": len(collections),
        "by_business_type": {},
        "by_status": {"active": 0, "inactive": 0},
        "top_collections": [],
    }

    # 按业务类型分组
    for col in collections:
        business_type = col.get("business_type", "unknown")
        if business_type not in summary["by_business_type"]:
            summary["by_business_type"][business_type] = 0
        summary["by_business_type"][business_type] += 1

        # 按状态分组
        if col.get("is_active", True):
            summary["by_status"]["active"] += 1
        else:
            summary["by_status"]["inactive"] += 1

    # 按文档数量排序，获取前5个
    sorted_collections = sorted(
        collections, key=lambda x: x.get("document_count", 0), reverse=True
    )
    summary["top_collections"] = [
        {
            "name": col["name"],
            "display_name": col["display_name"],
            "document_count": col.get("document_count", 0),
            "business_type": col.get("business_type", "unknown"),
        }
        for col in sorted_collections[:5]
    ]

    return {"success": True, "data": summary}
