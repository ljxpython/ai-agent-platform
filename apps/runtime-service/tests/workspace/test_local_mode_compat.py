import io
import zipfile
from pathlib import Path

from runtime_service.workspace.browser import WorkspaceBrowser


def test_local_workspace_browser_read_and_smart_zip(tmp_path: Path):
    # 1. 建立模拟本地工作区
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    uploads_dir = workspace_root / "uploads"
    uploads_dir.mkdir()

    # 写入普通文本文件
    text_file = workspace_root / "hello.txt"
    text_content = b"Hello, this is a local test workspace text file!"
    text_file.write_bytes(text_content)

    # 写入模拟 pptx 文件
    pptx_file = uploads_dir / "sample.pptx"
    pptx_content = b"PK\x03\x04" + b"A" * 1024  # 模拟 zip/pptx 魔数与内容
    pptx_file.write_bytes(pptx_content)

    browser = WorkspaceBrowser(workspace_root)

    # 2. 验证本地文件读取 read_file
    data, ref = browser.read_file("/workspace/hello.txt")
    assert data == text_content
    assert ref["file_name"] == "hello.txt"
    assert "sha256" in ref

    pptx_data, pptx_ref = browser.read_file("/workspace/uploads/sample.pptx")
    assert pptx_data == pptx_content
    assert pptx_ref["file_name"] == "sample.pptx"

    # 3. 验证本地工作区打包 create_archive (Smart Zip 策略)
    zip_bytes, zip_filename = browser.create_archive()
    assert zip_filename.endswith(".zip")
    assert len(zip_bytes) > 0

    # 校验 zip 结构和每个文件的压缩类型
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        infolist = {info.filename: info for info in zf.infolist()}
        assert "hello.txt" in infolist
        assert "uploads/sample.pptx" in infolist

        # 文本文件应走 ZIP_DEFLATED
        assert infolist["hello.txt"].compress_type == zipfile.ZIP_DEFLATED
        # pptx 已压缩文件应走 ZIP_STORED (零额外开销)
        assert infolist["uploads/sample.pptx"].compress_type == zipfile.ZIP_STORED

        # 验证解压数据精确匹配
        assert zf.read("hello.txt") == text_content
        assert zf.read("uploads/sample.pptx") == pptx_content


def test_local_workspace_tree_listing(tmp_path: Path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "sub").mkdir()
    (workspace_root / "sub" / "file.py").write_text("print(1)")

    browser = WorkspaceBrowser(workspace_root)
    page = browser.list_directory(path="/workspace")
    assert any(entry.name == "sub" for entry in page.items)

    sub_page = browser.list_directory(path="/workspace/sub")
    assert any(entry.name == "file.py" for entry in sub_page.items)


def test_local_workspace_http_endpoints(tmp_path: Path, monkeypatch):
    import asyncio

    import httpx
    from fastapi import FastAPI

    from runtime_service.http.workspace import router

    async def _run():
        # 1. 模拟本地工作区
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        uploads_dir = workspace_root / "uploads"
        uploads_dir.mkdir()
        (workspace_root / "readme.md").write_text("# Hello Local Workspace")
        (uploads_dir / "report.pptx").write_bytes(b"PK\x03\x04" + b"P" * 500)

        # 2. monkeypatch _auth 返回本地 Path，模拟本地模式
        async def fake_auth(thread_id, authorization, operation):
            return workspace_root

        monkeypatch.setattr("runtime_service.http.workspace._auth", fake_auth)

        app = FastAPI()
        app.include_router(router)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            # 3. 验证目录树接口
            res_tree = await client.get(
                "/internal/threads/test-thread/workspace/tree?path=/workspace"
            )
            assert res_tree.status_code == 200
            tree_data = res_tree.json()
            assert any(item["name"] == "readme.md" for item in tree_data["items"])
            assert any(item["name"] == "uploads" for item in tree_data["items"])

            # 4. 验证本地单文件下载
            res_file = await client.get(
                "/internal/threads/test-thread/workspace/content?path=/workspace/uploads/report.pptx"
            )
            assert res_file.status_code == 200
            assert res_file.content == b"PK\x03\x04" + b"P" * 500
            assert "Content-Disposition" in res_file.headers
            assert "report.pptx" in res_file.headers["Content-Disposition"]

            # 5. 验证本地整个工作区 Zip 打包下载
            res_zip = await client.get("/internal/threads/test-thread/workspace/zip")
            assert res_zip.status_code == 200
            assert res_zip.headers["content-type"] == "application/zip"
            with zipfile.ZipFile(io.BytesIO(res_zip.content), "r") as zf:
                assert "readme.md" in zf.namelist()
                assert "uploads/report.pptx" in zf.namelist()
                assert zf.read("readme.md") == b"# Hello Local Workspace"
                assert zf.read("uploads/report.pptx") == b"PK\x03\x04" + b"P" * 500

    asyncio.run(_run())
