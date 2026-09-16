"""Batch verification: durable image receipts, real sandbox PPTX, bounded publication."""
import asyncio
import base64
import io
import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from PIL import Image
from psycopg import sql
from psycopg.conninfo import make_conninfo
from runtime_service.services.dearflow_agent.external_task_storage import (
    ExternalTaskStorage,
)
from runtime_service.services.dearflow_agent.tools import media
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
)
from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.media import validate_media


@pytest.fixture
def storage():
    dsn = os.getenv("RUNTIME_MESSAGE_TEST_DSN", "postgresql://lijiaxin@127.0.0.1:5432/graphharbor_web_refactor_20260910")
    schema = "dear_p5_" + uuid4().hex
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    store = ExternalTaskStorage(make_conninfo(dsn, options=f"-c search_path={schema}"))
    store.initialize()
    try:
        yield store
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_durable_deduplication_fencing_restart_and_scope(storage):
    scope = ("tenant", "project", "user", "thread")
    def create(_):
        return storage.create(scope, "approved-image", "generate_image", {"prompt": "private"}, run_id="run", approval_ref="call")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, range(2)))
    assert sum(created for _, created in results) == 1
    identifier = str(results[0][0]["id"])
    with pytest.raises(ValueError, match="idempotency_conflict"):
        storage.create(scope, "approved-image", "generate_image", {"prompt": "changed"}, run_id="run", approval_ref="call")
    with pytest.raises(ValueError, match="not_found"):
        storage.get(("tenant", "other", "user", "thread"), identifier)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: storage.claim(identifier), range(2)))
    assert sum(row is not None for row in claims) == 1
    old = next(row for row in claims if row)
    with storage.connect() as db:
        db.execute("UPDATE dear_external_tasks SET lease_until=now()-interval '1 second' WHERE id=%s", (identifier,))
    restarted = ExternalTaskStorage(storage.dsn)
    assert restarted.claim(identifier) is None
    assert restarted.get(scope, identifier)["status"] == "unknown"
    assert not storage.finish(old, status="succeeded", result={"fake": True})
    assert "private" not in str(storage.stats())


def png(color="red"):
    output = io.BytesIO()
    Image.new("RGB", (64, 36), color).save(output, format="PNG")
    return output.getvalue()


def test_image_tools_idempotency_multi_reference_cancel_and_invalid_result(storage, tmp_path, monkeypatch):
    from runtime_service.tools import images
    monkeypatch.setenv("DATABASE_URI", storage.dsn)
    for name in ("IMAGE_25_KEY", "IMAGE_25_URL", "IMAGE_25_MODEL"):
        monkeypatch.setenv(name, "fixture")
    facts = SimpleNamespace(scope=SimpleNamespace(assistant_id="dearflow_agent", thread_id="thread"),
        principal=SimpleNamespace(tenant_id="tenant", project_id="project", user_id="user"))
    monkeypatch.setattr(media, "verified_delegation_from_user", lambda _: facts)
    runtime = SimpleNamespace(server_info=SimpleNamespace(user={}),
        execution_info=SimpleNamespace(thread_id="thread", run_id="run"), tool_call_id="approved-call")
    calls = []
    started = asyncio.Event()
    class Provider:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.images = self
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def generate(self, **kwargs):
            calls.append(kwargs)
            if kwargs["prompt"] == "cancel":
                started.set()
                await asyncio.Event().wait()
            payload = b"not an image" if kwargs["prompt"] == "invalid" else png()
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(payload).decode())])
        async def edit(self, **kwargs):
            return await self.generate(**kwargs)
    monkeypatch.setattr(images, "AsyncOpenAI", Provider)
    workspace = ImageWorkspace(tmp_path / "workspace")
    tools = {t.name: t for t in media.build_media_tools(workspace)}
    async def run():
        first = await tools["generate_image"].coroutine(prompt="one", idempotency_key="same", runtime=runtime)
        again = await tools["generate_image"].coroutine(prompt="one", idempotency_key="same", runtime=runtime)
        assert first == again and len(calls) == 1
        assert first["status"] == "succeeded"
        ref = first["result"]["runtime_images"][0]
        assert workspace.read_asset(ref["path"])[1] == ref
        edited = await tools["edit_image"].coroutine(image_path=ref["path"], prompt="edit", idempotency_key="edit", runtime=runtime,
                                                     reference_images=[ref["path"]])
        assert edited["status"] == "succeeded" and len(calls[-1]["image"]) == 2
        assert (await tools["generate_image"].coroutine(prompt="invalid", idempotency_key="invalid", runtime=runtime))["status"] == "unknown"
        before = len(calls)
        unknown = await tools["generate_image"].coroutine(prompt="invalid", idempotency_key="invalid", runtime=runtime)
        assert unknown["status"] == "unknown" and not unknown["result"] and len(calls) == before
        task = asyncio.create_task(tools["generate_image"].coroutine(prompt="cancel", idempotency_key="cancel", runtime=runtime))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        before = len(calls)
        assert (await tools["generate_image"].coroutine(prompt="cancel", idempotency_key="cancel", runtime=runtime))["status"] == "unknown"
        assert len(calls) == before
    asyncio.run(run())


def test_pptx_rejects_active_content_and_entities():
    def archive(extra="", relationship=""):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("ppt/presentation.xml", extra + '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldId/></p:presentation>')
            z.writestr("_rels/.rels", relationship or "<Relationships/>")
        return stream.getvalue()
    for data in (b"not a presentation", archive(relationship='<Relationships><Relationship TargetMode="External" Target="https://private"/></Relationships>'),
                 archive(extra='<!DOCTYPE p [<!ENTITY x "value">]>')):
        with pytest.raises(DocumentError):
            validate_media(data, "pptx")


@pytest.mark.skipif(os.getenv("DEAR_P5_DOCKER") != "1", reason="Enable real Docker sandbox verification")
def test_real_three_slide_pptx_and_missing_slide(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    backend = DearWorkspaceBackend("tenant", "project", str(uuid4()))
    backend.prepare()
    root = backend.root
    refs = [ImageWorkspace(root).save_asset(png(color), "generated") for color in ("red", "green", "blue")]
    (root / "work/plan.json").write_text(json.dumps({"aspect_ratio": "16:9", "slides": [{"title": str(i)} for i in range(3)]}))
    command = "python /skills/ppt-generation/scripts/generate.py --plan-file /workspace/work/plan.json --slide-images " + " ".join(ref["path"] for ref in refs) + " --output-file /workspace/work/deck.pptx"
    result = asyncio.run(backend.aexecute(command, timeout=60))
    assert result.exit_code == 0, result.output
    ref = ArtifactWorkspace(root).publish("/workspace/work/deck.pptx")
    data, read_ref = ArtifactWorkspace(root).read(ref["path"])
    assert ref == read_ref and ref["mime_type"].endswith("presentation")
    (root / "work/check.py").write_text('''from pptx import Presentation
from PIL import Image
from io import BytesIO
p=Presentation('/workspace/work/deck.pptx')
assert len(p.slides)==3
assert p.slide_width==12191695 and p.slide_height==6858000
pixels=[Image.open(BytesIO(s.shapes[0].image.blob)).getpixel((32,18)) for s in p.slides]
assert pixels[0][0]>200 and pixels[1][1]>100 and pixels[2][2]>200
print('three slides, dimensions, order verified')
''')
    result = asyncio.run(backend.aexecute("python /workspace/work/check.py", timeout=60))
    assert result.exit_code == 0, result.output
    result = asyncio.run(backend.aexecute(command.replace(refs[-1]["path"], "/workspace/missing.png"), timeout=60))
    assert result.exit_code != 0
    assert ArtifactWorkspace(root).read(ref["path"])[0] == data
    evidence = {"artifact": ref, "workspace": str(root), "image_refs": refs}
    Path(os.getenv("DEAR_P5_EVIDENCE", "/tmp/dear-p5-pptx.json")).write_text(json.dumps(evidence, indent=2))


def test_provider_accepts_but_drops_receipt_without_second_submission(storage, tmp_path, monkeypatch):
    """Real HTTP disconnect + real PostgreSQL; no paid provider or SDK replacement."""
    import socket
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    ledger = tmp_path / "accepted.jsonl"

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/v1/images/generations"
            with ledger.open("a") as stream:
                stream.write(json.dumps({"model": payload["model"], "accepted": True}) + "\n")
            # The supplier accepted the request; TCP closes before any HTTP response.
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            self.close_connection = True

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setenv("DATABASE_URI", storage.dsn)
    monkeypatch.setenv("IMAGE_25_KEY", "synthetic-key")
    monkeypatch.setenv("IMAGE_25_MODEL", "synthetic-image")
    monkeypatch.setenv("IMAGE_25_URL", f"http://127.0.0.1:{server.server_port}/v1")
    facts = SimpleNamespace(
        scope=SimpleNamespace(assistant_id="dearflow_agent", thread_id="thread"),
        principal=SimpleNamespace(tenant_id="tenant", project_id="project", user_id="user"),
    )
    monkeypatch.setattr(media, "verified_delegation_from_user", lambda _: facts)
    runtime = SimpleNamespace(
        server_info=SimpleNamespace(user={}),
        execution_info=SimpleNamespace(thread_id="thread", run_id="first-run"),
        tool_call_id="approved-call",
    )
    workspace = ImageWorkspace(tmp_path / "workspace")

    async def run():
        tools = {t.name: t for t in media.build_media_tools(workspace)}
        first = await tools["generate_image"].coroutine(
            prompt="synthetic accepted purchase", idempotency_key="receipt-lost", runtime=runtime,
        )
        assert first["status"] == "unknown" and not first["result"]
        assert len(ledger.read_text().splitlines()) == 1
        # Reconstruct the tools/storage and retry from a different Run after the failure.
        runtime.execution_info.run_id = "resumed-run"
        tools = {t.name: t for t in media.build_media_tools(workspace)}
        repeated = await asyncio.gather(*[
            tools["generate_image"].coroutine(
                prompt="synthetic accepted purchase", idempotency_key="receipt-lost", runtime=runtime,
            ) for _ in range(3)
        ])
        assert all(result == first for result in repeated)
        polled = await tools["get_media_task"].coroutine(task_id=first["task_id"], runtime=runtime)
        assert polled == first
        row = ExternalTaskStorage(storage.dsn).get(("tenant", "project", "user", "thread"), first["task_id"])
        assert row["attempts"] == 1 and row["status"] == "unknown"
        assert len(ledger.read_text().splitlines()) == 1
        assert not (workspace.root / "generated").exists()
        print("V08: supplier accepted=1; TCP receipt lost; resumed concurrent submissions=3; supplier total=1; persisted attempts=1/status=unknown")

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
