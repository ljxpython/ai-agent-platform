"""
RAG-Anything integration helpers for LightRAG API.

This module keeps multimodal processing at the API layer so the core
LightRAG retrieval/indexing pipeline remains unchanged.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Optional

from lightrag.lightrag import LightRAG
from lightrag.utils import logger


MULTIMODAL_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".webp",
}


class RAGAnythingProcessor:
    """Small adapter that bridges LightRAG API and RAG-Anything."""

    def __init__(
        self,
        rag: LightRAG,
        parser: str = "docling",
        parse_method: str = "auto",
        parser_output_dir: Optional[str] = None,
        enable_multimodal: bool = False,
        vision_model_func: Any = None,
    ) -> None:
        self.rag = rag
        self.parser = parser
        self.parse_method = parse_method
        self.parser_output_dir = parser_output_dir or "./parser_output"
        self.enable_multimodal = enable_multimodal
        self.vision_model_func = vision_model_func
        self._raganything = None

    @staticmethod
    def _is_image_file(file_path: Path) -> bool:
        return file_path.suffix.lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".tiff",
            ".tif",
            ".gif",
            ".webp",
        }

    async def _process_image_with_vision_model(
        self,
        file_path: Path,
        track_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        if self.vision_model_func is None:
            logger.warning(
                f"No vision model configured for image {file_path.name}; multimodal image processing cannot proceed."
            )
            return False, track_id, None

        try:
            image_data = base64.b64encode(file_path.read_bytes()).decode("utf-8")
            prompt = (
                "Analyze this image for retrieval-augmented generation. "
                "Produce a dense factual description in plain text. "
                "Include visible text (OCR), key objects, layout, tables/charts if any, "
                "relationships between important elements, and concise semantic tags."
            )
            description = await self.vision_model_func(
                prompt,
                system_prompt=(
                    "You are extracting high-value factual content from an image for indexing. "
                    "Do not answer conversationally. Output compact, information-dense prose."
                ),
                history_messages=[],
                image_data=image_data,
            )

            if not description or not str(description).strip():
                logger.warning(
                    f"Vision model returned empty content for image {file_path.name}"
                )
                return False, track_id, None

            await self.rag.apipeline_enqueue_documents(
                input=str(description),
                file_paths=file_path.name,
                metadata_list=[metadata] if metadata is not None else None,
                track_id=track_id,
            )
            await self.rag.apipeline_process_enqueue_documents()
            logger.info(
                f"Image processed via direct vision-model fallback: {file_path.name}"
            )
            return True, track_id, None
        except Exception as exc:
            logger.error(
                f"Vision-model image processing failed for {file_path.name}: {exc}"
            )
            logger.debug("Vision fallback exception details", exc_info=True)
            return False, track_id, None

    def _ensure_initialized(self) -> None:
        if self._raganything is not None:
            return

        from raganything import RAGAnything
        from raganything.config import RAGAnythingConfig

        config = RAGAnythingConfig(
            parser=self.parser,
            parse_method=self.parse_method,
            parser_output_dir=self.parser_output_dir,
            enable_image_processing=self.enable_multimodal,
            enable_table_processing=self.enable_multimodal,
            enable_equation_processing=self.enable_multimodal,
            display_content_stats=False,
        )

        self._raganything = RAGAnything(
            lightrag=self.rag,
            config=config,
            vision_model_func=self.vision_model_func,
        )

    def should_use_raganything(self, file_path: Path) -> bool:
        if not self.enable_multimodal:
            return False
        return file_path.suffix.lower() in MULTIMODAL_EXTENSIONS

    async def parse_and_process_document(
        self,
        file_path: Path,
        track_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        pipeline_status: Optional[dict] = None,
        pipeline_status_lock: Optional[Any] = None,
        **kwargs: Any,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        try:
            if self._is_image_file(file_path):
                return await self._process_image_with_vision_model(
                    file_path, track_id, metadata
                )

            self._ensure_initialized()

            if pipeline_status_lock and pipeline_status:
                async with pipeline_status_lock:
                    msg = f"Parsing document with RAG-Anything ({self.parser})..."
                    pipeline_status["latest_message"] = msg
                    pipeline_status["history_messages"].append(msg)

            content_list, doc_id = await self._raganything.parse_document(
                file_path=str(file_path),
                output_dir=self.parser_output_dir,
                parse_method=self.parse_method,
                display_stats=False,
                **kwargs,
            )

            if pipeline_status_lock and pipeline_status:
                async with pipeline_status_lock:
                    msg = f"Parsed {len(content_list)} multimodal content blocks"
                    pipeline_status["latest_message"] = msg
                    pipeline_status["history_messages"].append(msg)

            await self._raganything.insert_content_list(
                content_list=content_list,
                doc_id=doc_id,
                file_path=str(file_path),
                track_id=track_id,
            )

            try:
                current_doc_status = await self.rag.doc_status.get_by_id(doc_id)
                if current_doc_status:
                    merged_metadata = {}
                    if isinstance(current_doc_status.get("metadata"), dict):
                        merged_metadata.update(current_doc_status["metadata"])
                    if isinstance(metadata, dict):
                        merged_metadata.update(metadata)
                    await self.rag.doc_status.upsert(
                        {
                            doc_id: {
                                **current_doc_status,
                                "track_id": track_id,
                                "metadata": merged_metadata,
                            }
                        }
                    )
                    await self.rag.doc_status.index_done_callback()
            except Exception as exc:
                logger.warning(
                    f"Failed to write track_id back to doc_status for {file_path.name}: {exc}"
                )

            logger.info(
                f"RAG-Anything processed {file_path.name} successfully, doc_id={doc_id}"
            )
            return True, track_id, doc_id
        except Exception as exc:
            logger.error(f"RAG-Anything processing failed for {file_path.name}: {exc}")
            logger.debug("RAG-Anything exception details", exc_info=True)

            if pipeline_status_lock and pipeline_status:
                async with pipeline_status_lock:
                    msg = f"RAG-Anything processing error: {exc}"
                    pipeline_status["latest_message"] = msg
                    pipeline_status["history_messages"].append(msg)

            return False, track_id, None


def create_raganything_processor(
    rag: LightRAG,
    enable_multimodal: bool = False,
    parser: str = "docling",
    parse_method: str = "auto",
    parser_output_dir: Optional[str] = None,
    vision_model_func: Any = None,
) -> Optional[RAGAnythingProcessor]:
    if not enable_multimodal:
        return None

    try:
        import raganything  # noqa: F401
    except ImportError:
        logger.warning(
            "RAG-Anything is not installed. Multimodal processing will stay disabled."
        )
        return None

    return RAGAnythingProcessor(
        rag=rag,
        parser=parser,
        parse_method=parse_method,
        parser_output_dir=parser_output_dir,
        enable_multimodal=enable_multimodal,
        vision_model_func=vision_model_func,
    )
