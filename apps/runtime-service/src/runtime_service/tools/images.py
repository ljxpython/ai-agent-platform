"""Bounded image IO and provider calls, independent of any demo agent."""

from __future__ import annotations

import asyncio
import base64
import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from langchain_core.tools import ToolException, tool
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI, OpenAIError
from pydantic import SecretStr

from runtime_service.observability.usage import usage_only_config
from runtime_service.runtime.pii import PiiRedactionConfig, redact_text
from runtime_service.tools.errors import tool_error_handler
from runtime_service.workspace.image_io import (
    MAX_BYTES,
    image_type,
)
from runtime_service.workspace.image_io import (
    ImageWorkspace as ImageWorkspace,
)
from runtime_service.workspace.image_io import (
    ImageWorkspaceError as ImageWorkspaceError,
)


async def download_image(url: str, *, allowed_hosts: set[str]) -> bytes:
    """Only accept operator-approved asset hosts; no redirects or ambient credentials."""
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in allowed_hosts
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Unapproved asset URL")
        async with (
            httpx.AsyncClient(timeout=45, trust_env=False) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes(65536):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("Oversized image")
        image_type(bytes(data))
        return bytes(data)
    except (httpx.HTTPError, ValueError, ToolException):
        raise ToolException(
            "Image download failed; check the configured asset host and image size."
        ) from None


def setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ToolException(f"Runtime image setting {name} is missing.")
    return value


def resolve_vision_config() -> tuple[str, str, str, int]:
    """Resolve vision provider settings: supports VISION_*, DEEPSEEK_*, and legacy DOUBAO_*."""
    # 1. Generic VISION_* configs have highest precedence
    model = os.environ.get("VISION_MODEL", "").strip()
    api_key = os.environ.get("VISION_API_KEY", "").strip()
    base_url = (
        os.environ.get("VISION_API_BASE", "").strip()
        or os.environ.get("VISION_BASE_URL", "").strip()
    )

    # 2. DeepSeek official / proxy configs (defaults to deepseek-flash with multimodal capability)
    if not (model and api_key and base_url):
        ds_key = (
            os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("DEEPSEEK_PROXY_API_KEY", "").strip()
        )
        if ds_key:
            model = (
                model
                or os.environ.get("DEEPSEEK_VISION_MODEL", "").strip()
                or "deepseek-flash"
            )
            api_key = api_key or ds_key
            base_url = (
                base_url
                or os.environ.get("DEEPSEEK_URL", "").strip()
                or os.environ.get("DEEPSEEK_PROXY_URL", "").strip()
                or "https://api.deepseek.com"
            )

    # 3. Fallback to legacy DOUBAO_* configs
    if not (model and api_key and base_url):
        model = model or os.environ.get("DOUBAO_MODEL", "").strip()
        api_key = api_key or os.environ.get("DOUBAO_API_KEY", "").strip()
        base_url = base_url or os.environ.get("DOUBAO_API_BASE", "").strip()

    max_tokens_raw = (
        os.environ.get("VISION_MAX_TOKENS", "").strip()
        or os.environ.get("DOUBAO_MAX_TOKENS", "").strip()
        or "2048"
    )
    try:
        max_tokens = min(int(max_tokens_raw), 4096)
    except ValueError:
        max_tokens = 2048

    if not model or not api_key or not base_url:
        missing = []
        if not model:
            missing.append(
                "model (VISION_MODEL / DEEPSEEK_VISION_MODEL / DOUBAO_MODEL)"
            )
        if not api_key:
            missing.append(
                "api_key (VISION_API_KEY / DEEPSEEK_API_KEY / DOUBAO_API_KEY)"
            )
        if not base_url:
            missing.append(
                "base_url (VISION_API_BASE / DEEPSEEK_URL / DOUBAO_API_BASE)"
            )
        raise ToolException(
            f"Runtime vision configuration is missing: {', '.join(missing)}."
        )

    return model, api_key, base_url, max_tokens


def build_image_tools(
    workspace: ImageWorkspace,
    pii_config: PiiRedactionConfig | None = None,
):
    async def _extract_and_save_image(
        result: Any, operation: str
    ) -> tuple[str, dict[str, Any]]:
        if not getattr(result, "data", None):
            raise ToolException("image_submission_unknown")
        item = result.data[0]
        if getattr(item, "b64_json", None):
            if len(item.b64_json) > MAX_BYTES * 4 // 3 + 4:
                raise ToolException("image_submission_unknown")
            data = base64.b64decode(item.b64_json, validate=True)
        elif getattr(item, "url", None):
            try:
                hosts = {
                    host.strip()
                    for host in setting("RUNTIME_IMAGE_ASSET_HOSTS").split(",")
                }
                data = await download_image(item.url, allowed_hosts=hosts)
            except ToolException:
                # The provider already accepted the purchase; never imply a safe retry.
                raise ToolException("image_submission_unknown") from None
        else:
            raise ToolException("image_submission_unknown")
        try:
            ref = await asyncio.to_thread(workspace.save_asset, data, "generated")
        except ToolException as exc:
            raise ToolException("image_submission_unknown") from exc
        return ref["path"], {"runtime_images": [ref]}

    def _handle_image_provider_error(exc: Exception) -> ToolException:
        if isinstance(exc, ToolException):
            return exc
        if not isinstance(exc, OpenAIError):
            raise exc
        body = getattr(exc, "body", None)
        if isinstance(body, dict) and body.get("code") == "content_policy_violation":
            return ToolException("image_content_policy_violation")
        return ToolException("image_submission_unknown")

    @tool(response_format="content_and_artifact")
    async def generate_image(prompt: str) -> tuple[str, dict[str, Any]]:
        """Generate an image from a prompt after human approval; return its /workspace path."""
        if not prompt.strip() or len(prompt) > 8000:
            raise ToolException("Prompt must contain 1 to 8000 characters.")
        try:
            async with AsyncOpenAI(
                api_key=setting("IMAGE_25_KEY"),
                base_url=setting("IMAGE_25_URL"),
                timeout=180,
                max_retries=0,
            ) as client:
                result = await client.images.generate(
                    model=setting("IMAGE_25_MODEL"),
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
            return await _extract_and_save_image(result, "Image generation")
        except Exception as exc:
            raise _handle_image_provider_error(exc) from None

    @tool(response_format="content_and_artifact")
    async def edit_image(
        image_path: str, prompt: str, reference_images: list[str] | None = None
    ) -> tuple[str, dict[str, Any]]:
        """Edit or transform an existing image in /workspace based on prompt after human approval; return its /workspace path."""
        if not prompt.strip() or len(prompt) > 8000:
            raise ToolException("Prompt must contain 1 to 8000 characters.")
        if len(reference_images or []) > 3:
            raise ToolException(
                "At most three additional reference images are supported."
            )
        try:
            data = await asyncio.to_thread(workspace.read, image_path)
            _, mime = image_type(data)
            ext = (
                "png"
                if mime == "image/png"
                else ("jpg" if mime == "image/jpeg" else "webp")
            )
            file_tuple = (f"image.{ext}", data, mime)
            files = [file_tuple]
            for index, path in enumerate(reference_images or []):
                reference = await asyncio.to_thread(workspace.read, path)
                extension, content_type = image_type(reference)
                files.append(
                    (f"reference-{index}.{extension}", reference, content_type)
                )
            async with AsyncOpenAI(
                api_key=setting("IMAGE_25_KEY"),
                base_url=setting("IMAGE_25_URL"),
                timeout=180,
                max_retries=0,
            ) as client:
                result = await client.images.edit(
                    model=setting("IMAGE_25_MODEL"),
                    image=files if reference_images else file_tuple,
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
            return await _extract_and_save_image(result, "Image editing")
        except Exception as exc:
            raise _handle_image_provider_error(exc) from None

    @tool
    async def analyze_image(
        image_path: str, question: str = "Describe this image."
    ) -> str:
        """Understand a PNG/JPEG/WebP file inside /workspace using the vision model. Read-only."""
        if not question.strip() or len(question) > 8000:
            raise ToolException("Question must contain 1 to 8000 characters.")
        try:
            safe_question = redact_text(question, pii_config)
            if not isinstance(safe_question, str):
                raise ToolException("image_analysis_unavailable")
            data = await asyncio.to_thread(workspace.read, image_path)
            _, mime = image_type(data)
            model_name, api_key, base_url, max_tokens = resolve_vision_config()
            model = ChatOpenAI(
                model=model_name,
                api_key=SecretStr(api_key),
                base_url=base_url,
                max_completion_tokens=max_tokens,
                timeout=60,
                max_retries=0,
                stream_usage=True,
                metadata={
                    "runtime_usage_model": {
                        "model_id": None,
                        "provider": "openai",
                        "model_name": model_name,
                        "pricing": None,
                    }
                },
            )
            result = await model.ainvoke(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": safe_question},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{base64.b64encode(data).decode()}"
                                },
                            },
                        ],
                    }
                ],
                config=usage_only_config("vision"),
            )
            text_content = result.text or (
                result.content if isinstance(result.content, str) else ""
            )
            if not text_content and isinstance(result.content, list):
                for block in result.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_content += block.get("text", "")
            return text_content or "No textual description returned by vision model."
        except ToolException:
            raise
        except (OpenAIError, httpx.HTTPError) as exc:
            raise ToolException("image_analysis_unavailable") from exc

    for image_tool in (generate_image, edit_image, analyze_image):
        image_tool.handle_tool_error = tool_error_handler(image_tool.name)
    return [generate_image, edit_image, analyze_image]
