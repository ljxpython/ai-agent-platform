from __future__ import annotations

import base64
import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage

from runtime_service.tools.images import ImageWorkspace, build_image_tools


class ImageToolsMiddleware(HumanInTheLoopMiddleware):
    def __init__(self, workspace: ImageWorkspace):
        super().__init__(
            interrupt_on={
                "generate_image": {
                    "allowed_decisions": ["approve", "reject"],
                },
                "edit_image": {
                    "allowed_decisions": ["approve", "reject"],
                },
            }
        )
        self.workspace = workspace
        self.tools = build_image_tools(workspace)

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        clean_messages = []
        for msg in getattr(request, "messages", []):
            if isinstance(msg, HumanMessage) and isinstance(msg.content, list):
                new_blocks = []
                for block in msg.content:
                    if isinstance(block, dict):
                        # 物化旧 Base64 块
                        if block.get("type") == "image" and block.get("data"):
                            try:
                                raw_data = base64.b64decode(block["data"])
                                sha = hashlib.sha256(raw_data).hexdigest()
                                ref = self.workspace.put_upload(raw_data, sha)
                                new_blocks.append({
                                    "type": "text",
                                    "text": f"[图片附件] {ref['path']}",
                                })
                                continue
                            except Exception:
                                pass
                        # 剥离 extras 仅留 text 给模型
                        if block.get("type") == "text":
                            new_blocks.append({
                                "type": "text",
                                "text": str(block.get("text", "")),
                            })
                            continue
                    new_blocks.append(block)
                clean_messages.append(msg.model_copy(update={"content": new_blocks}))
            else:
                clean_messages.append(msg)

        clean_request = (
            request.override(messages=clean_messages)
            if hasattr(request, "override")
            else request
        )
        return await handler(clean_request)
