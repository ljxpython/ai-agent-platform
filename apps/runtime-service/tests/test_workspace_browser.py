import base64
import io
import json
import os
import zipfile

import pytest
from PIL import Image
from runtime_service.workspace.artifact_refs import ARTIFACT_MIMES, ArtifactWorkspace
from runtime_service.workspace.browser import PREVIEW_BYTES, WorkspaceBrowser
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
from runtime_service.workspace.html_preview import safe_html


def test_tree_pagination_mutation_and_unsafe_files(tmp_path):
    (tmp_path / "work").mkdir()
    for name in ("a.yaml", "b.py", "c.md"):
        (tmp_path / "work" / name).write_text("value: 1")
    (tmp_path / "work/link").symlink_to("/etc/passwd")
    os.mkfifo(tmp_path / "work/pipe")
    browser = WorkspaceBrowser(tmp_path)
    page = browser.list_directory("/workspace/work", limit=2)
    assert [x.name for x in page.items] == ["a.yaml", "b.py"]
    assert (
        browser.list_directory("/workspace/work", cursor=page.next_cursor).items[0].name
        == "c.md"
    )
    (tmp_path / "work/d.txt").write_text("new")
    with pytest.raises(DocumentError, match="workspace_directory_changed"):
        browser.list_directory("/workspace/work", cursor=page.next_cursor)
    for path in (
        "/etc/passwd",
        "/workspace/../x",
        "/workspace/work/link",
        "/workspace/work/pipe",
        "/workspace/work/./a.yaml",
        "/workspace/work/a\x00",
    ):
        with pytest.raises(DocumentError):
            browser.read_file(path)
    for cursor in ("invalid!", base64.b64encode(b"[]").decode()):
        with pytest.raises(DocumentError, match="invalid_workspace_cursor"):
            browser.list_directory("/workspace/work", cursor=cursor)


def test_preview_download_and_limits(tmp_path):
    browser = WorkspaceBrowser(tmp_path)
    (tmp_path / "code.py").write_text("x = 1")
    preview, mime = browser.preview("/workspace/code.py")
    assert mime == "application/json"
    assert json.loads(preview)["text"] == "x = 1"
    (tmp_path / "big.txt").write_text("中" * PREVIEW_BYTES)
    payload = json.loads(browser.preview("/workspace/big.txt")[0])
    assert payload["truncated"] and "�" not in payload["text"]
    (tmp_path / "data.bin").write_bytes(b"\0\1")
    assert (
        browser.read_file("/workspace/data.bin")[1]["mime_type"]
        == "application/octet-stream"
    )
    with pytest.raises(DocumentError, match="preview_unsupported"):
        browser.preview("/workspace/data.bin")
    (tmp_path / "bad.txt").write_bytes(b"\0")
    with pytest.raises(DocumentError, match="invalid_document"):
        browser.preview("/workspace/bad.txt")
    with (tmp_path / "huge.txt").open("wb") as target:
        target.truncate(20 * 1024 * 1024 + 1)
    with pytest.raises(DocumentError, match="file_too_large"):
        browser.read_file("/workspace/huge.txt")


@pytest.mark.parametrize(
    "extension",
    [
        "yaml",
        "yml",
        "toml",
        "xml",
        "py",
        "sh",
        "sql",
        "ts",
        "jsx",
        "tsx",
        "vue",
        "svg",
        "java",
        "c",
        "cpp",
        "rs",
        "md",
        "html",
        "css",
        "js",
        "txt",
        "bib",
        "csv",
        "json",
    ],
)
def test_text_artifacts_persist_and_publish_idempotently(tmp_path, extension):
    (tmp_path / "work").mkdir()
    source = tmp_path / "work" / ("payment." + extension)
    source.write_text('{"value": 1}')
    store = ArtifactWorkspace(tmp_path)
    ref = store.publish("/workspace/work/" + source.name)
    assert ref == store.publish("/workspace/work/" + source.name)
    assert ref["mime_type"] == ARTIFACT_MIMES[extension]
    assert ArtifactWorkspace(tmp_path).list_artifacts()["items"] == [ref]
    assert ArtifactWorkspace(tmp_path).read(ref["path"])[0] == source.read_bytes()
    source.write_text('{"value": 2}')
    assert store.publish("/workspace/work/" + source.name)["sha256"] != ref["sha256"]


@pytest.mark.parametrize(
    "extension,format",
    [("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("webp", "WEBP")],
)
def test_generated_images_and_type_mismatch(tmp_path, extension, format):
    (tmp_path / "generated").mkdir()
    source = tmp_path / "generated" / ("image." + extension)
    image = Image.new("RGB", (2, 2))
    image.save(source, format=format)
    assert (
        ArtifactWorkspace(tmp_path).publish("/workspace/generated/" + source.name)[
            "preview_kind"
        ]
        == "image"
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG" if format != "PNG" else "JPEG")
    source.write_bytes(buffer.getvalue())
    with pytest.raises(DocumentError, match="type_mismatch"):
        ArtifactWorkspace(tmp_path).publish("/workspace/generated/" + source.name)


def test_html_has_no_active_navigation_or_script():
    html = safe_html(
        '<meta http-equiv="refresh" content="0;url=https://evil.test">'
        '<base href="https://evil.test"><script>fetch("https://evil.test")</script>'
        '<a href="https://evil.test"><b onclick="alert(1)">hello</b></a>'
        '<iframe src="https://evil.test"></iframe><img src="https://evil.test/a">'
        '<div style="color:red">diagram</div>'
    )
    assert "https://evil.test" not in html
    assert "onclick" not in html and "<script" not in html and "<iframe" not in html
    assert "Content-Security-Policy" in html and "diagram" in html


def test_upload_policy_does_not_expand_with_artifacts(tmp_path):
    with pytest.raises(DocumentError, match="unsupported_file_type"):
        DocumentWorkspace(tmp_path).put(b"x: 1", "a" * 64, "application/yaml")


def test_document_and_archive_publication(tmp_path):
    import fitz

    (tmp_path / "work").mkdir()
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(tmp_path / "work/report.pdf")
    with zipfile.ZipFile(tmp_path / "work/source.zip", "w") as archive:
        archive.writestr("main.py", "print(1)")
    with zipfile.ZipFile(tmp_path / "work/book.xlsx", "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    (tmp_path / "work/book.xls").write_bytes(
        bytes.fromhex("d0cf11e0a1b11ae1") + b"fixture"
    )
    with zipfile.ZipFile(tmp_path / "work/deck.pptx", "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "ppt/presentation.xml",
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="r1"/></p:sldIdLst></p:presentation>',
        )
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/></Relationships>',
        )
        archive.writestr("ppt/slides/slide1.xml", "<slide/>")
    store = ArtifactWorkspace(tmp_path)
    for name in ("report.pdf", "source.zip", "book.xlsx", "book.xls", "deck.pptx"):
        ref = store.publish("/workspace/work/" + name)
        assert ref["preview_kind"] == "download"
        assert store.read(ref["path"])[0] == (tmp_path / "work" / name).read_bytes()


def test_directory_replaced_with_symlink_is_not_followed(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "result.txt").write_text("inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "result.txt").write_text("outside")
    browser = WorkspaceBrowser(tmp_path)
    open_directory = browser.io._directory

    def replace_after_open(parts, **kwargs):
        fd = open_directory(parts, **kwargs)
        work.rename(tmp_path / "old-work")
        work.symlink_to(outside, target_is_directory=True)
        return fd

    monkeypatch.setattr(browser.io, "_directory", replace_after_open)
    assert browser.read_file("/workspace/work/result.txt")[0] == b"inside"
    monkeypatch.setattr(browser.io, "_directory", open_directory)
    with pytest.raises(DocumentError):
        browser.read_file("/workspace/work/result.txt")


def test_published_versions_and_tampering(tmp_path):
    from runtime_service.tools.artifacts import build_artifact_tool

    (tmp_path / "work").mkdir()
    source = tmp_path / "work/report.md"
    source.write_bytes(b"# report\n")
    store = ArtifactWorkspace(tmp_path)
    assert store.list_artifacts()["items"] == []
    ref = build_artifact_tool(tmp_path).invoke({"file_path": "/workspace/work/report.md"})
    source.write_bytes(b"# changed\n")
    newer = store.publish("/workspace/work/report.md")
    assert newer["path"] != ref["path"]
    assert store.read(ref["path"])[0] == b"# report\n"
    (tmp_path / "work/report.txt").write_bytes(b"# report\n")
    alternate = store.publish("/workspace/work/report.txt")
    assert alternate["artifact_id"] == ref["artifact_id"]
    assert {item["path"] for item in store.list_artifacts()["items"]} == {
        item["path"] for item in (ref, newer, alternate)
    }
    (tmp_path / ref["path"].removeprefix("/workspace/")).write_bytes(b"tampered")
    with pytest.raises(DocumentError) as error:
        store.read(ref["path"])
    assert (error.value.code, error.value.status_code) == ("artifact_hash_mismatch", 409)


def test_artifact_pagination_and_failed_publication(tmp_path):
    (tmp_path / "work").mkdir()
    source = tmp_path / "work/report.md"
    store = ArtifactWorkspace(tmp_path)
    expected = set()
    for index in range(101):
        source.write_text(f"report {index}")
        expected.add(store.publish("/workspace/work/report.md")["path"])
    first = store.list_artifacts(limit=100)
    second = store.list_artifacts(cursor=first["next_cursor"], limit=100)
    assert len(first["items"]) == 100 and len(second["items"]) == 1
    assert second["next_cursor"] is None
    paths = [item["path"] for item in first["items"] + second["items"]]
    assert paths == sorted(expected)
    revision = (tmp_path / "outputs").stat().st_mtime_ns
    source.write_text("another report")
    store.publish("/workspace/work/report.md")
    # Deterministic even on filesystems with coarse timestamp resolution.
    os.utime(tmp_path / "outputs", ns=(revision + 1_000_000_000,) * 2)
    with pytest.raises(DocumentError, match="workspace_directory_changed"):
        store.list_artifacts(cursor=first["next_cursor"])
    before = set((tmp_path / "outputs").iterdir())
    (tmp_path / "work/bad.png").write_bytes(b"not an image")
    with pytest.raises(DocumentError):
        store.publish("/workspace/work/bad.png")
    assert set((tmp_path / "outputs").iterdir()) == before


def test_readable_filename_artifacts_in_outputs(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    doc = outputs / "01-header-and-strategy.md"
    doc.write_text("# Architecture Design\n", encoding="utf-8")
    (outputs / ".publish-temp").write_text("ignored", encoding="utf-8")

    store = ArtifactWorkspace(tmp_path)
    listed = store.list_artifacts()
    assert len(listed["items"]) == 1
    item = listed["items"][0]
    assert item["file_name"] == "01-header-and-strategy.md"
    assert item["path"] == "/workspace/outputs/01-header-and-strategy.md"
    assert item["preview_kind"] == "markdown"
    assert len(item["sha256"]) == 64

    browser = WorkspaceBrowser(tmp_path)
    raw_bytes, ref = browser.read_file(item["path"])
    assert raw_bytes == b"# Architecture Design\n"
    assert ref["file_name"] == "01-header-and-strategy.md"
    assert ref["sha256"] == item["sha256"]

    preview_bytes, mime = browser.preview(item["path"])
    assert mime == "application/json"
    assert json.loads(preview_bytes)["text"] == "# Architecture Design\n"

