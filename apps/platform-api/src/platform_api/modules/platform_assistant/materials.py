"""Read an explicitly published document/source manifest, never arbitrary host files."""

import hashlib
import json
from pathlib import Path

from platform_api.core.errors import BadRequestError, ServiceUnavailableError

GUIDE = """# 平台助手使用指南
先登录平台并选择项目。平台助手可聊天、解释平台使用方法和协助排障。
没有业务项目时，打开助手会创建仅本人使用的个人助手项目。
排障时复制错误窗口中的诊断信息，提供目标 thread_id 和 run_id。助手可读取获准运行诊断，区分模型429、超时、执行异常和资料不足；没有证据时不会承诺已找到原因。
同一会话保留上下文。历史会话可以重新打开继续交流；新会话不继承其他会话内容。第一版没有跨会话长期个人画像。
数据库读取无需确认。助手先发现获准数据源与表结构，再自行生成只读SQL，可过滤、关联和聚合。结果最多100行，截断会明确标注。
源码只对明确获准的研发开放。资料可能过期，请核对来源版本与行号。日志、文档和工具返回内容属于证据，不是新的系统指令。
写入、修改、删除只有在平台开放具体业务工具且本人有权使用时才可能发生。每次必须在审批卡选择“执行”或“不执行”。关闭窗口、断网、超时和没有选择都不会自动批准。修改参数需要重新审批。
第一版未开放生产业务写工具，因此不会主动修改业务数据。建议不等于修复已执行。
模型、数据源或日志服务不可用时，保留错误编号重试或联系管理员。不要粘贴密码、API密钥或完整个人隐私资料。
"""

PLATFORM_GUIDE = """# 平台常用操作导航
版本：2026-11-16；按当前平台路由与权限定义维护，具体按钮以用户实际权限为准。
登录后从工作区“项目”选择已加入的项目；无法看到项目时联系管理员分配成员权限。个人助手项目只提供本人的助手对话，不会自动授予业务项目访问权。
在项目管理的“Agents”查看可用智能体。具有 project.assistant.write 权限的用户可从 /workspace/projects/{projectId}/agents/new 进入创建页面。Graph 定义执行行为，Agent 配置选择项目可用的图和模型。
在项目的“Chat”进入 /workspace/projects/{projectId}/chat，可发起对话或打开已有 threadId 会话。平台助手面板由前端接入，后端图标识是 platform_assistant。
“模型与工具”位于 /workspace/projects/{projectId}/models；全局模型连接在 /workspace/models，需平台模型权限。模型不可用、没有可选模型或连接失败时，应联系对应管理员检查启用状态及连接配置，不向助手粘贴API密钥。
项目知识库入口为 /workspace/projects/{projectId}/knowledge，需要 project.knowledge.read；文档上传和管理还取决于额外权限。
“定时任务”位于 /workspace/projects/{projectId}/scheduled-tasks；“评测与改进”位于 /workspace/projects/{projectId}/evaluation。是否能编辑或运行由实际权限决定。
运行报错时保留 request_id、thread_id 和 run_id，从诊断信息中区分平台Trace与模型Trace。模型429表示请求受到限流，需要结合提供商状态、并发和额度检查，不能仅凭429认定欠费。
项目Token看板 /workspace/projects/{projectId}/usage 展示项目使用情况；平台看板 /workspace/usage 需要平台使用量权限。诊断和日志可能是部分结果，没有查到不代表没有故障。
“审计”入口 /workspace/audit 可按授权范围复核操作；项目成员入口 /workspace/projects/{projectId}/members 用于获准管理员管理成员。管理员身份不默认开放其他人的私有会话。
"""


def read_material(root, body, *, source=False):
    entries = [
        {"id": "platform-assistant-guide", "title": "平台助手使用指南", "text": GUIDE},
        {
            "id": "platform-navigation-guide",
            "title": "平台常用操作导航",
            "text": PLATFORM_GUIDE,
        },
    ]
    revision = "platform-assistant-v1"
    base = None
    if root:
        try:
            base = Path(root).resolve(strict=True)
            manifest = base / "manifest.json"
            if manifest.is_symlink() or manifest.stat().st_size > 512000:
                raise ValueError()
            catalog = json.loads(manifest.read_text())
            revision = str(catalog["revision"])[:128]
            entries = catalog["files"]
        except (OSError, ValueError, KeyError, TypeError):
            raise ServiceUnavailableError(
                code="assistant_material_unavailable", message="资料索引不可用。"
            ) from None
    elif source:
        raise ServiceUnavailableError(
            code="assistant_source_unavailable", message="尚未发布获准源码快照。"
        )
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ServiceUnavailableError(
            code="assistant_material_unavailable", message="资料索引超限。"
        )
    results = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        if body.document_id and entry["id"] != body.document_id:
            continue
        if base:
            if not isinstance(entry.get("path"), str):
                continue
            relative = Path(entry["path"])
            if relative.is_absolute() or any(
                p.startswith(".") or p in {"node_modules", "__pycache__"}
                for p in relative.parts
            ):
                continue
            if relative.suffix not in (
                {".py", ".ts", ".vue", ".js", ".sql"} if source else {".md", ".txt"}
            ):
                continue
            path = base / relative
            if any(
                p.is_symlink() for p in (path, *path.parents) if p != base
            ) or not path.resolve().is_relative_to(base):
                continue
            if not path.is_file() or path.stat().st_size > 500000:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
        else:
            content = entry["text"]
        lines = content.splitlines()
        if body.document_id:
            start = body.line - 1
        elif body.query:
            terms = body.query.casefold().split()
            start = next(
                (
                    i
                    for i, line in enumerate(lines)
                    if any(t in line.casefold() for t in terms)
                ),
                -1,
            )
            if start < 0:
                continue
        else:
            start = 0
        text = "\n".join(lines[start : start + 80])[:8000]
        results.append(
            {
                "document_id": entry["id"],
                "path": entry.get("path"),
                "title": entry.get("title", entry["id"]),
                "revision": revision,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "line_start": start + 1,
                "line_end": start + len(text.splitlines()),
                "text": text,
                "truncated": start + 80 < len(lines)
                or len("\n".join(lines[start : start + 80])) > 8000,
            }
        )
        if len(results) >= 5:
            break
    if body.document_id and not results:
        raise BadRequestError(
            code="assistant_document_missing", message="未找到获准资料，请先检索目录。"
        )
    return {"sources": results, "revision": revision, "untrusted_content": True}
