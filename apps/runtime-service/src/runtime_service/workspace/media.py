"""Validate image-based PPTX before publishing immutable artifacts."""
from runtime_service.workspace.documents import DocumentError

MAX_MEDIA_BYTES = 20 * 1024 * 1024
MEDIA_MIMES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
}


def validate_media(data: bytes, extension: str) -> None:
    if extension in {"png", "jpg", "jpeg", "webp"}:
        from langchain_core.tools import ToolException

        from runtime_service.tools.images import image_type
        try:
            _, mime = image_type(data)
        except ToolException as exc:
            raise DocumentError("invalid_artifact_image", 415) from exc
        if mime != MEDIA_MIMES[extension]:
            raise DocumentError("artifact_image_type_mismatch", 415)
        return
    if extension != "pptx" or not data or len(data) > MAX_MEDIA_BYTES:
        raise DocumentError("presentation_size_or_type", 413)
    import posixpath
    from xml.etree import ElementTree

    from runtime_service.workspace.archives import read_zip
    try:
        entries = dict(read_zip(data))
        if not {"[Content_Types].xml", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"} <= entries.keys():
            raise ValueError("invalid_presentation")
        for name, content in entries.items():
            if name.endswith((".xml", ".rels")):
                text = content.decode("utf-8-sig")
                if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                    raise ValueError("xml_entities_denied")
                root = ElementTree.fromstring(text)
                if any(node.get("TargetMode") == "External" for node in root.iter()):
                    raise ValueError("external_presentation_relationship")
            if name.lower().endswith("vbaproject.bin"):
                raise ValueError("macro_presentation_denied")
        root = ElementTree.fromstring(entries["ppt/presentation.xml"])
        slides = root.findall(".//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId")
        if not 1 <= len(slides) <= 20:
            raise ValueError("presentation_slide_limit")
        relations = {node.get("Id"): node for node in ElementTree.fromstring(entries["ppt/_rels/presentation.xml.rels"])}
        targets = []
        for slide in slides:
            relation = relations.get(slide.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
            if relation is None or not relation.get("Type", "").endswith("/slide"):
                raise ValueError("missing_slide_relationship")
            target = posixpath.normpath(posixpath.join("ppt", relation.get("Target", "")))
            if not target.startswith("ppt/slides/") or target not in entries:
                raise ValueError("missing_slide")
            targets.append(target)
        if len(set(targets)) != len(slides):
            raise ValueError("duplicate_slide")
    except (ValueError, ElementTree.ParseError) as exc:
        raise DocumentError("invalid_presentation", 422) from exc
