"""Opt-in real Docker boundaries; resources belong only to this test invocation."""

import asyncio
import hashlib
import io
import json
import os
import shlex
import subprocess
import time
import zipfile

import pytest
from workspace.test_office_documents import docx_bytes, pptx_bytes

from runtime_service.tools.documents import build_document_tools
from runtime_service.workspace.document_reader import DOCX_MIME, PPTX_MIME
from runtime_service.workspace.documents import DocumentWorkspace
from runtime_service.workspace.execution import execute_in_workspace


@pytest.fixture
def image():
    value = os.getenv("OFFICE_TEST_IMAGE")
    if not value:
        pytest.skip("OFFICE_TEST_IMAGE enables real Docker verification")
    subprocess.run(
        ["docker", "inspect", value], check=True, capture_output=True, timeout=10
    )
    return value


@pytest.mark.parametrize(
    "mime,raw",
    [
        (DOCX_MIME, docx_bytes("Docker DOCX 125 中文", table=True)),
        (PPTX_MIME, pptx_bytes("Docker PPTX 125 中文", "")),
    ],
    ids=["docx", "pptx"],
)
def test_real_office_tool(image, tmp_path, mime, raw):
    (tmp_path / "work").mkdir()
    ref = DocumentWorkspace(tmp_path).put(raw, hashlib.sha256(raw).hexdigest(), mime)
    start = time.monotonic()
    tool = build_document_tools(tmp_path, execution_image=image)[0]
    result = asyncio.run(tool.ainvoke({"file_path": ref["path"]}))
    assert isinstance(result, dict), result
    assert "125 中文" in result["text"]
    assert not list((tmp_path / "work").iterdir())
    print(
        json.dumps(
            {
                "format": result["format"],
                "sha256": ref["sha256"],
                "bytes": len(raw),
                "duration_ms": round((time.monotonic() - start) * 1000),
                "text_chars": len(result["text"]),
            }
        )
    )


def test_real_isolation_timeout_output_and_memory(image, tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "uploads").mkdir()
    source = tmp_path / "uploads" / "original"
    source.write_text("preserved")
    script = """import json, pathlib, resource, socket
checks = {}
for key, path in [("root", "/blocked"), ("upload", "/workspace/uploads/blocked")]:
    try:
        pathlib.Path(path).write_text("bad")
        checks[key] = False
    except OSError:
        checks[key] = True
try:
    socket.create_connection(("1.1.1.1", 443), timeout=1)
    checks["network"] = False
except OSError:
    checks["network"] = True
checks["rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps(checks))"""
    result = asyncio.run(
        execute_in_workspace(
            tmp_path, "python -c " + shlex.quote(script), image=image, protected=True
        )
    )
    assert result.exit_code == 0 and all(
        json.loads(result.output)[key] for key in ("root", "upload", "network")
    )
    timeout = asyncio.run(
        execute_in_workspace(
            tmp_path, "sleep 5", image=image, protected=True, timeout=1
        )
    )
    assert timeout.exit_code != 0
    overflow = asyncio.run(
        execute_in_workspace(
            tmp_path, "python -c 'print(\"x\" * 200000)'", image=image, protected=True
        )
    )
    assert overflow.truncated and len(overflow.output.encode()) <= 128 * 1024
    memory = asyncio.run(
        execute_in_workspace(
            tmp_path,
            "python -c 'x = bytearray(512 * 1024 * 1024)'",
            image=image,
            protected=True,
        )
    )
    assert memory.exit_code != 0
    assert source.read_text() == "preserved"


def test_cancel_removes_only_its_container(image, tmp_path, monkeypatch):
    from runtime_service.workspace import execution

    (tmp_path / "work").mkdir()
    names = []
    original = execution.docker_workspace_args

    def capture(*args, **kwargs):
        names.append(kwargs["name"])
        return original(*args, **kwargs)

    monkeypatch.setattr(execution, "docker_workspace_args", capture)

    async def run():
        task = asyncio.create_task(
            execute_in_workspace(tmp_path, "sleep 30", image=image, protected=True)
        )
        await asyncio.sleep(2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(names) == 1
    check = subprocess.run(
        ["docker", "inspect", names[0]], capture_output=True, timeout=10
    )
    assert check.returncode != 0
    assert tmp_path.is_dir()


def test_large_document_and_two_scopes_capacity(image, tmp_path):
    raw = docx_bytes("bounded capacity 125")
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as target,
    ):
        for name in source.namelist():
            target.writestr(name, source.read(name))
        for index in range(9):
            target.writestr(f"bounded-{index}.bin", os.urandom(2 * 1024 * 1024))
    large = output.getvalue()
    timings, uploads = [], []
    roots = [tmp_path / "first", tmp_path / "second"]
    refs = []
    for root, data in zip(roots, (large, docx_bytes("other scope 999")), strict=True):
        (root / "work").mkdir(parents=True)
        start = time.monotonic()
        refs.append(
            DocumentWorkspace(root).put(
                data, hashlib.sha256(data).hexdigest(), DOCX_MIME
            )
        )
        uploads.append(round((time.monotonic() - start) * 1000))

    async def read(index):
        start = time.monotonic()
        result = await build_document_tools(roots[index], execution_image=image)[
            0
        ].ainvoke({"file_path": refs[index]["path"]})
        timings.append(round((time.monotonic() - start) * 1000))
        assert isinstance(result, dict), result
        assert ("125" if index == 0 else "999") in result["text"]
        return result

    async def run():
        for _ in range(5):
            await read(0)
        results = await asyncio.gather(read(0), read(1))
        assert "999" not in results[0]["text"] and "125" not in results[1]["text"]
        denied = await build_document_tools(roots[1], execution_image=image)[0].ainvoke(
            {"file_path": refs[0]["path"]}
        )
        assert "tool.invalid_input" in denied
        script = (
            'import json,resource,sys,time; sys.path.insert(0,"/opt/runtime-reader"); '
            "from runtime_service.workspace.document_reader import _read_source,read_office; "
            "request = " + repr({"file_path": refs[0]["path"]}) + "; "
            "start = time.process_time(); raw,mime = _read_source(request); "
            "result = read_office(raw,mime,request); "
            'print(json.dumps({"rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, '
            '"cpu_seconds": round(time.process_time()-start,3), "text_chars": len(result["text"])}))'
        )
        measured = await execute_in_workspace(
            roots[0],
            "python -c " + shlex.quote(script),
            image=image,
            protected=True,
        )
        assert measured.exit_code == 0, measured.output
        stats = json.loads(measured.output)
        assert 0 < stats["rss_kib"] < 256 * 1024 and stats["text_chars"] > 0
        return stats

    stats = asyncio.run(run())
    ordered = sorted(timings[:5])
    print(
        json.dumps(
            {
                "large_bytes": len(large),
                "upload_ms": uploads,
                "parse_ms": timings,
                "p50_ms": ordered[2],
                "sample_p95_ms": ordered[-1],
                "parallel_containers": 2,
                "parallel_memory_limit_mib": 512,
                "parallel_cpu_limit": 2,
                **stats,
            }
        )
    )


def test_image_without_reader_never_falls_back_to_host(image, tmp_path):
    subprocess.run(
        ["docker", "inspect", "python:3.13-slim"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    (tmp_path / "work").mkdir()
    raw = docx_bytes("must not run on host")
    ref = DocumentWorkspace(tmp_path).put(
        raw, hashlib.sha256(raw).hexdigest(), DOCX_MIME
    )
    result = asyncio.run(
        build_document_tools(tmp_path, execution_image="python:3.13-slim")[0].ainvoke(
            {"file_path": ref["path"]}
        )
    )
    assert "tool.operation_failed" in result
    assert not list((tmp_path / "work").iterdir())
