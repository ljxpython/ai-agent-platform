"""Opt-in real platform Worker and isolated Ubuntu RAG; setup is explicit and owned."""

import hashlib
import json
import os
import secrets
import shlex
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

SUBMIT = "mcp_submit_project_knowledge_document"
QUERY = "mcp_query_project_knowledge"
pytestmark = pytest.mark.skipif(
    os.getenv("KNOWLEDGE_DOCUMENTS_PLATFORM_LIVE") != "1",
    reason="requires this Worktree's registered stack and isolated document RAG",
)


def tool_text(message):
    content = message["content"]
    return (
        content
        if isinstance(content, str)
        else "".join(block["text"] for block in content if block.get("type") == "text")
    )


class LiveDocuments:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[4]
        self.out = self.root / ".local-stack/evidence/knowledge-platform-documents"
        environment = json.loads(
            (self.root / ".local-stack/environment.json").read_text()
        )
        assert Path(environment["root"]).resolve() == self.root
        resources = json.loads((self.out / "resources.json").read_text())
        self.projects = resources["projects"]
        self.client = httpx.Client(
            base_url=f"http://127.0.0.1:{environment['ports']['PLATFORM_API_PORT']}",
            trust_env=False,
            timeout=60,
        )
        self.admin = self.login("admin", "admin123456")
        self.client.headers.update(self.admin)
        self.client.headers["x-project-id"] = self.projects["alpha"]
        private = self.out / "actors.private.json"
        if private.exists():
            self.actors = json.loads(private.read_text())
        else:
            self.actors = {}
            for name, role in (
                ("uploader", "project_executor"),
                ("reader", "project_editor"),
            ):
                actor = {
                    "username": "knowledge_docs_" + uuid4().hex[:12],
                    "password": secrets.token_urlsafe(24),
                }
                created = self.request("POST", "/api/users", json=actor)
                actor["id"] = created["id"]
                self.request(
                    "PUT",
                    f"/api/projects/{self.projects['alpha']}/members/{actor['id']}",
                    json={"role": role},
                )
                self.actors[name] = actor
            private.write_text(json.dumps(self.actors))
            private.chmod(0o600)
        self.uploader = self.login(
            **{k: self.actors["uploader"][k] for k in ("username", "password")}
        )
        self.reader = self.login(
            **{k: self.actors["reader"][k] for k in ("username", "password")}
        )
        models = self.request("GET", "/api/runtime/models")["models"]
        self.context = {
            "model_id": next(
                m["id"]
                for m in models
                if m["enabled"] and m["model"] == "deepseek-v4.1-flash"
            ),
            "max_tokens": 2048,
        }
        agents_file = self.out / "agents.json"
        if agents_file.exists():
            self.agents = json.loads(agents_file.read_text())
        else:
            available = self.request(
                "GET", f"/api/projects/{self.projects['alpha']}/agents"
            )["items"]
            self.agents = {
                graph: next(
                    agent["id"] for agent in available if agent["graph_id"] == graph
                )
                for graph in ("showcase_demo", "dearflow_agent")
            }
            agents_file.write_text(json.dumps(self.agents))

    def request(self, method, path, *, expected=200, **kwargs):
        response = self.client.request(method, path, **kwargs)
        assert response.status_code == expected, {
            "path": path,
            "status": response.status_code,
            "body": response.text[:1200],
        }
        return response.json() if response.content else None

    def login(self, username, password):
        value = self.request(
            "POST",
            "/api/identity/session",
            json={"username": username, "password": password},
        )
        return {"Authorization": "Bearer " + value["tokens"]["access_token"]}

    def save(self, name, payload):
        (self.out / (name + ".json")).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def thread(self, graph="showcase_demo", *, headers=None):
        return self.request(
            "POST",
            "/api/langgraph/threads",
            headers=headers or self.uploader,
            json={
                "graph_id": graph,
                "metadata": {"agent_id": self.agents[graph], "access_policy": "review"},
            },
        )["thread_id"]

    def state(self, thread, *, headers=None):
        return self.request(
            "GET",
            f"/api/langgraph/threads/{thread}/state",
            headers=headers or self.uploader,
        )

    def command(self, thread, method, params, *, headers=None, expected=200):
        result = self.request(
            "POST",
            f"/api/langgraph/threads/{thread}/commands",
            expected=expected,
            headers={
                **(headers or self.uploader),
                "Idempotency-Key": "document-" + uuid4().hex,
            },
            json={"id": 1, "method": method, "params": params},
        )
        return result["result"]["run_id"] if expected == 200 else result

    def start(
        self, thread, prompt, graph="showcase_demo", *, headers=None, context=None
    ):
        return self.command(
            thread,
            "run.start",
            {
                "assistant_id": graph,
                "context": context or self.context,
                "input": {"messages": [{"role": "user", "content": prompt}]},
            },
            headers=headers,
        )

    def terminal(self, thread, run, *, headers=None):
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            value = self.request(
                "GET",
                f"/api/langgraph/threads/{thread}/runs/{run}",
                headers=headers or self.uploader,
            )
            if value["status"] in {"success", "error", "interrupted", "timeout"}:
                return value
            time.sleep(0.5)
        raise AssertionError(
            {"thread": thread, "run": run, "failure": "worker_deadline"}
        )

    def approve(self, thread):
        state = self.state(thread)
        pending = state.get("interrupts") or [
            item
            for task in state.get("tasks", [])
            for item in task.get("interrupts", [])
        ]
        if isinstance(pending, dict):
            pending = [
                {"id": k, "value": v.get("value", v)} for k, v in pending.items()
            ]
        assert len(pending) == 1
        assert pending[0]["value"]["action_requests"][0]["name"] == SUBMIT
        return self.command(
            thread,
            "input.respond",
            {"resume": {pending[0]["id"]: {"decisions": [{"type": "approve"}]}}},
        )

    def upload(self, thread, raw, mime, name):
        digest = hashlib.sha256(raw).hexdigest()
        kind = "images" if mime.startswith("image/") else "files"
        return self.request(
            "PUT",
            f"/api/langgraph/threads/{thread}/{kind}/uploads/{digest}",
            headers={**self.uploader, "Content-Type": mime},
            params={"file_name": name},
            content=raw,
        )

    def submit(self, case, raw, mime, name, graph="showcase_demo"):
        thread = self.thread(graph)
        ref = self.upload(thread, raw, mime, name)
        prompt = (
            "用户明确要求把此附件共享到当前项目知识库。请立即且仅调用一次 mcp_submit_project_knowledge_document，参数 file_ref 使用下方完整 JSON。不要读取、解析、改写或复制文件，不要调用其他工具。工具返回后说明任务已受理即可，不要查询任务、不等待入库。附件引用：\n"
            + json.dumps(ref, ensure_ascii=False)
        )
        started = time.monotonic()
        run = self.start(thread, prompt, graph)
        evidence = {"thread_id": thread, "run_id": run, "graph": graph, "file_ref": ref}
        self.save(case + "-started", evidence)
        try:
            terminal = self.terminal(thread, run)
            assert terminal["status"] == "interrupted", terminal
            before = self.state(thread)
            assert not any(
                m.get("name") == SUBMIT for m in before["values"]["messages"]
            )
            resumed = self.approve(thread)
            terminal = self.terminal(thread, resumed)
            state = self.state(thread)
            self.save(case + "-state", state)
            assert terminal["status"] == "success", terminal
            calls = [m for m in state["values"]["messages"] if m.get("name") == SUBMIT]
            assert len(calls) == 1
            body = calls[0]["artifact"]["structured_content"]
            assert body == json.loads(tool_text(calls[0]))
            assert calls[0].get("status", "success") != "error", body
            assert body["file_name"] == name
            evidence.update(
                approval_run_id=resumed,
                receipt=body,
                before_approval_no_receipt=True,
                seconds=round(time.monotonic() - started, 3),
            )
            self.save(case, evidence)
            return evidence
        except BaseException:
            self.save(case + "-failure", {**evidence, "state": self.state(thread)})
            raise

    def ready(self, receipt):
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            value = self.request(
                "GET",
                f"/api/projects/{self.projects['alpha']}/knowledge/jobs/{receipt['job_id']}",
                headers=self.reader,
            )
            if value["status"] in {"ready", "failed"}:
                assert value["status"] == "ready", value
                assert value["searchable"] is True
                return value
            time.sleep(2)
        raise AssertionError({"job": receipt["job_id"], "failure": "rag_deadline"})

    def query(self, name, prompt, *, headers=None, sources_version=2):
        headers = headers or self.reader
        thread = self.thread(headers=headers)
        run = self.start(
            thread,
            "请只实际调用一次 mcp_query_project_knowledge 查询以下资料，top_k=8；不要使用任何其他工具。仅根据返回来源简短回答并列出引用。问题："
            + prompt,
            headers=headers,
        )
        terminal = self.terminal(thread, run, headers=headers)
        state = self.state(thread, headers=headers)
        self.save(name + "-state", state)
        assert terminal["status"] == "success", terminal
        calls = [m for m in state["values"]["messages"] if m.get("name") == QUERY]
        assert len(calls) == 1
        result = calls[0]["artifact"]["structured_content"]
        assert result == json.loads(tool_text(calls[0]))
        assert result["status"] == "ok"
        assert result.get("sources_version", 1) == sources_version
        assert all(
            "sources_version" not in call.get("args", {})
            for message in state["values"]["messages"]
            for call in message.get("tool_calls", [])
        )
        assert len(tool_text(calls[0]).encode()) <= 12 * 1024
        assert all(len(s["preview"]) <= 800 for s in result["sources"])
        self.save(name, {"thread_id": thread, "run_id": run, "result": result})
        return result

    def configure(self, sources_version, upload):
        from dotenv import set_key

        for name, settings in (
            (
                "runtime",
                {
                    "RUNTIME_KNOWLEDGE_SOURCES_VERSION": str(sources_version),
                    "RUNTIME_KNOWLEDGE_UPLOAD_ENABLED": str(int(upload)),
                },
            ),
            (
                "platform",
                {"PLATFORM_API_KNOWLEDGE_UPLOAD_ENABLED": str(upload).lower()},
            ),
        ):
            for key, value in settings.items():
                set_key(self.root / ".local-stack" / (name + ".env"), key, value)
        for service in ("platform-api", "runtime-worker", "runtime-api"):
            self.restart(service)

    def counts(self):
        resources = json.loads((self.out / "resources.json").read_text())
        path = resources["remote_state"] + "/corpus/control/knowledge.sqlite3"
        script = f"import sqlite3,json; db=sqlite3.connect({path!r}); print(json.dumps({{table: db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ['usage','jobs','documents','requests']}}))"
        raw = subprocess.check_output(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "sshmy2",
                "python3 -c " + shlex.quote(script),
            ],
            text=True,
        )
        return json.loads(raw)

    @contextmanager
    def pause_next_builder(self):
        resources = json.loads((self.out / "resources.json").read_text())
        script = """
import json, os, select, signal, sys, time
from pathlib import Path
parent, root = int(sys.argv[1]), sys.argv[2]
assert root in Path(f'/proc/{parent}/cmdline').read_text().replace('\\x00', ' ')
child = None
try:
    deadline = time.monotonic() + 120
    while child is None and time.monotonic() < deadline:
        for candidate in Path(f'/proc/{parent}/task/{parent}/children').read_text().split():
            try:
                args = Path(f'/proc/{candidate}/cmdline').read_bytes().split(b'\\0')
            except FileNotFoundError:
                continue
            if b'src.knowledge.job_worker' in args and (root + '/corpus/control/knowledge.sqlite3').encode() in args:
                child = int(candidate)
                os.kill(child, signal.SIGSTOP)
                print(json.dumps({'child': child, 'paused': True}), flush=True)
                break
        time.sleep(.01)
    assert child is not None, 'owned_builder_not_started'
    select.select([sys.stdin], [], [], 300)
finally:
    if child is not None:
        try: os.kill(child, signal.SIGCONT)
        except ProcessLookupError: pass
"""
        process = subprocess.Popen(
            [
                "rtk",
                "proxy",
                "ssh",
                "-o",
                "BatchMode=yes",
                "sshmy2",
                "python3 -c "
                + shlex.quote(script)
                + " "
                + shlex.quote(str(resources["pid"]))
                + " "
                + shlex.quote(resources["remote_state"]),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            yield process
        finally:
            process.stdin.close()
            process.wait(timeout=15)
            assert process.returncode == 0, "owned builder pause/release failed"

    def frozen_checksums(self, namespace=""):
        resources = json.loads((self.out / "resources.json").read_text())
        script = """
import hashlib, json, sqlite3, sys
from pathlib import Path
root=Path(sys.argv[1]) / 'corpus'
db=sqlite3.connect(root / 'control/knowledge.sqlite3')
view=sys.argv[3] or db.execute('SELECT active_namespace FROM projects WHERE id=?',(sys.argv[2],)).fetchone()[0]
paths=root/view
print(json.dumps({'namespace':view,'files':{str(p.relative_to(paths)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.rglob('*') if p.is_file()}}))
"""
        value = subprocess.check_output(
            [
                "rtk",
                "proxy",
                "ssh",
                "-o",
                "BatchMode=yes",
                "sshmy2",
                "python3 -c "
                + shlex.quote(script)
                + " "
                + shlex.quote(resources["remote_state"])
                + " "
                + shlex.quote(resources["kbs"]["alpha"])
                + " "
                + shlex.quote(namespace),
            ],
            text=True,
        )
        result = json.loads(value)
        assert result["files"]
        return result

    def generation_action(self, action, namespace=""):
        resources = json.loads((self.out / "resources.json").read_text())
        script = """
import asyncio, contextlib, io, json, logging, os, sys
from pathlib import Path
from dotenv import dotenv_values
state=Path(sys.argv[1])
assert state.parent == Path('/home/ubuntu/.local/state/rag-anything-use') and state.name.startswith('platform-6394-')
env=dotenv_values('/home/ubuntu/.local/state/rag-anything-use/platform-e2e-off-20261013/knowledge.env')
os.environ.update({k:v for k,v in env.items() if v is not None})
os.environ['KNOWLEDGE_ROOT_DIR']=str(state/'corpus')
sys.path.insert(0,'/home/ubuntu/PyCharmMiscProject/rag-anything-use')
logging.getLogger('lightrag').disabled=True
from src.knowledge.config import build_knowledge_service_config
from src.knowledge.jobs import KnowledgeJobStore
from src.knowledge.generations import KnowledgeGenerationService
config=build_knowledge_service_config()
store=KnowledgeJobStore(config)
kb=sys.argv[2]
async def run():
    generations=KnowledgeGenerationService(store)
    try:
        if sys.argv[3]=='inspect':
            with store.connect() as db:
                return {'active':store.project(kb)['active_namespace'],'generations':[r[0] for r in db.execute('SELECT namespace FROM generations WHERE kb=? ORDER BY created_at',(kb,))]}
        if sys.argv[3]=='enable':
            store.enable(kb,True)
        else:
            store.enable(kb,False)
            await generations.rollback(kb,sys.argv[4])
        return {'active':store.project(kb)['active_namespace'],'documents':store.list_documents(kb)}
    finally: await generations.close()
with contextlib.redirect_stdout(io.StringIO()):
    result=asyncio.run(run())
print(json.dumps(result))
"""
        # This interpreter belongs to the RAG source, never the platform or union environment.
        command = (
            shlex.quote(
                "/home/ubuntu/PyCharmMiscProject/rag-anything-use/.venv/bin/python"
            )
            + " -c "
            + shlex.quote(script)
        )
        command += (
            " "
            + shlex.quote(resources["remote_state"])
            + " "
            + shlex.quote(resources["kbs"]["alpha"])
            + " "
            + shlex.quote(action)
            + " "
            + shlex.quote(namespace)
        )
        value = subprocess.check_output(
            ["rtk", "proxy", "ssh", "-o", "BatchMode=yes", "sshmy2", command],
            text=True,
            timeout=60,
        )
        return json.loads(value)

    def restart(self, service):
        subprocess.run(
            [
                "rtk",
                "proxy",
                "bash",
                str(self.root / "scripts/local-stack.sh"),
                "restart-one",
                service,
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )


@pytest.fixture
def live_documents():
    live = LiveDocuments()
    try:
        yield live
    finally:
        live.client.close()


def test_real_member_documents_images_and_v2(live_documents):
    live = live_documents
    cases = [
        (
            "old-text",
            b"# Orion backup policy\nOrion backup retention is 35 days. Restoration drills happen every 14 days. Public marker PLATFORM-6394-OLD.",
            "text/markdown",
            "fixture-old.md",
            "showcase_demo",
        ),
        ("pdf", "text.pdf", "application/pdf", "fixture-new.pdf", "showcase_demo"),
        (
            "docx",
            "handbook.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "fixture-handbook.docx",
            "showcase_demo",
        ),
        (
            "pptx",
            "release.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "fixture-release.pptx",
            "showcase_demo",
        ),
        ("png", "recovery.png", "image/png", "fixture-recovery.png", "dearflow_agent"),
        ("jpeg", "recovery.jpg", "image/jpeg", "fixture-recovery.jpg", "showcase_demo"),
    ]
    completed = []
    for case, source, mime, name, graph in cases:
        ready_file = live.out / (case + "-ready.json")
        if ready_file.exists():
            evidence = json.loads((live.out / (case + ".json")).read_text())
        else:
            evidence = live.submit(
                case,
                source
                if isinstance(source, bytes)
                else (live.out / "fixtures" / source).read_bytes(),
                mime,
                name,
                graph,
            )
            ready = live.ready(evidence["receipt"])
            live.save(case + "-ready", ready)
        completed.append(evidence)
        print(case, evidence["receipt"]["status"], "→ ready", flush=True)
    ids = {e["receipt"]["document_id"] for e in completed}
    documents = live.request(
        "GET",
        f"/api/projects/{live.projects['alpha']}/knowledge/documents",
        headers=live.reader,
    )["items"]
    assert ids.issubset({d["document_id"] for d in documents})
    old_new = live.query(
        "reader-old-new-v2", "Orion backup retention and restoration drill interval"
    )
    assert {
        completed[0]["receipt"]["document_id"],
        completed[1]["receipt"]["document_id"],
    }.issubset({s["document_id"] for s in old_new["sources"]})
    pdf_sources = [
        s
        for s in old_new["sources"]
        if s["document_id"] == completed[1]["receipt"]["document_id"]
    ]
    assert any(
        s["locator"]["unit"] == "page" and s["locator"]["start"] >= 1
        for s in pdf_sources
    )
    image = live.query(
        "reader-images-v2",
        "Orion emergency recovery code DR-4826 and recovery time objective 45 minutes",
    )
    assert {
        completed[4]["receipt"]["document_id"],
        completed[5]["receipt"]["document_id"],
    }.issubset({s["document_id"] for s in image["sources"]})
    assert any(s["locator"]["unit"] == "unknown" for s in image["sources"])
    live.save(
        "formats-result",
        {
            "model": "deepseek-v4.1-flash",
            "member_roles": ["project_executor", "project_editor"],
            "documents": [
                {
                    "name": c[3],
                    "document_id": e["receipt"]["document_id"],
                    "receipt_status": e["receipt"]["status"],
                }
                for c, e in zip(cases, completed, strict=True)
            ],
            "v2_old_new": True,
            "v2_images": True,
            "bytes_limits": {"documents": 20 * 1024**2, "images": 5 * 1024**2},
        },
    )


def test_real_dedup_fork_restart_permissions_and_stop(live_documents):
    live = live_documents
    source = json.loads((live.out / "png.json").read_text())
    receipt = live.ready(source["receipt"])
    before = live.counts()
    # A fresh Run and Thread owns a new request key; ready content must still reuse the RAG job.
    duplicate = live.submit(
        "duplicate-image",
        (live.out / "fixtures/recovery.png").read_bytes(),
        "image/png",
        "fixture-recovery.png",
        "dearflow_agent",
    )
    assert duplicate["receipt"]["reused"] is True
    assert duplicate["receipt"]["job_id"] == receipt["job_id"]
    assert duplicate["receipt"]["searchable"] is True
    after = live.counts()
    assert before["usage"] == after["usage"] and before["jobs"] == after["jobs"]
    live.save(
        "dedup-counts", {"before": before, "after": after, "extra_model_events": 0}
    )

    history = live.request(
        "POST",
        f"/api/langgraph/threads/{source['thread_id']}/history",
        headers=live.uploader,
        json={"limit": 30},
    )
    # Fork before the prior receipt, so the model actually exercises the copied upload trust.
    checkpoint = next(
        state["checkpoint"]["checkpoint_id"]
        for state in history
        if state.get("next") == ["model"]
        and all(m["type"] == "human" for m in state["values"]["messages"])
    )
    fork = live.request(
        "POST",
        f"/api/langgraph/threads/{source['thread_id']}/fork",
        headers=live.uploader,
        json={"checkpoint_id": checkpoint, "title": "knowledge-image-fork"},
    )["thread_id"]
    graph = "dearflow_agent"
    run = live.start(
        fork,
        "用户明确将附件共享到项目知识库。只调用一次 mcp_submit_project_knowledge_document，file_ref="
        + json.dumps(source["file_ref"], ensure_ascii=False)
        + "。不要读取/解析图片或轮询。",
        graph,
    )
    terminal = live.terminal(fork, run)
    live.save(
        "fork-before-restart",
        {"thread_id": fork, "run_id": run, "state": live.state(fork)},
    )
    assert terminal["status"] == "interrupted", terminal
    live.restart("runtime-worker")
    live.restart("runtime-api")
    resumed = live.approve(fork)
    assert live.terminal(fork, resumed)["status"] == "success"
    fork_state = live.state(fork)
    calls = [m for m in fork_state["values"]["messages"] if m.get("name") == SUBMIT]
    body = calls[-1]["artifact"]["structured_content"]
    assert (
        body["reused"] is True
        and body["file_name"] == "fixture-recovery.png"
        and body["job_id"] == receipt["job_id"]
    )
    assert live.counts()["usage"] == after["usage"]
    live.save(
        "fork-restart",
        {
            "thread_id": fork,
            "resumed_run_id": resumed,
            "receipt": body,
            "receipt_and_approval_survive_restart": True,
        },
    )

    # Project job reads survive upload shutdown and do not grant access to another project.
    cross = live.request(
        "GET",
        f"/api/projects/{live.projects['beta']}/knowledge/jobs/{receipt['job_id']}",
        headers={**live.admin, "x-project-id": live.projects["beta"]},
        expected=404,
    )
    mismatch = live.request(
        "GET",
        f"/api/projects/{live.projects['alpha']}/knowledge/jobs/{receipt['job_id']}",
        headers={**live.uploader, "x-project-id": live.projects["beta"]},
        expected=400,
    )
    assert mismatch["error"]["code"] == "project_scope_mismatch"
    live.save(
        "cross-project", {"admin_other_kb": cross, "member_other_scope_denied": True}
    )

    grant = f"/api/projects/{live.projects['alpha']}/members/{live.actors['uploader']['id']}"
    live.request("DELETE", grant)
    try:
        live.request(
            "GET",
            f"/api/projects/{live.projects['alpha']}/knowledge/jobs/{receipt['job_id']}",
            headers=live.uploader,
            expected=403,
        )
        denied = live.command(
            source["thread_id"],
            "run.start",
            {
                "assistant_id": graph,
                "input": {"messages": [{"role": "user", "content": "共享资料"}]},
            },
            expected=403,
        )
        assert live.counts()["usage"] == after["usage"]
        live.save("member-revoked", {"denial": denied, "extra_model_events": 0})
    finally:
        live.request("PUT", grant, json={"role": "project_executor"})

    # Plan mode cannot acquire mutation tools, even with an explicit upload request.
    thread = live.thread()
    plan = {**live.context, "plan_mode": True}
    run = live.start(
        thread,
        "请仅说明如何把图片共享入知识库，当前是计划模式，不要提交计划、不调用工具。",
        context=plan,
    )
    status = live.terminal(thread, run)["status"]
    assert status in {"success", "interrupted"}
    assert not any(
        m.get("name") == SUBMIT for m in live.state(thread)["values"]["messages"]
    )
    assert live.counts()["jobs"] == after["jobs"]
    live.save("plan-mode", {"status": status, "no_knowledge_mutation": True})


def test_real_large_file_async_and_chat_stop(live_documents):
    live = live_documents
    raw = (live.out / "fixtures/boundary-20MiB.pdf").read_bytes()
    assert len(raw) == 20 * 1024**2
    submitted = live.submit("large-file", raw, "application/pdf", "boundary-20MiB.pdf")
    assert submitted["receipt"]["status"] in {
        "queued",
        "parsing",
        "indexing",
        "publishing",
        "ready",
    }
    thread = submitted["thread_id"]
    # Stop only the chat; the already accepted project ingest remains durable and searchable.
    stopped = live.request(
        "POST",
        f"/api/langgraph/threads/{thread}/cancel",
        expected=202,
        headers={**live.uploader, "Idempotency-Key": "knowledge-stop-" + uuid4().hex},
        json={},
    )
    ready = live.ready(submitted["receipt"])
    live.save(
        "large-file-stop",
        {
            "file_bytes": len(raw),
            "initial_status": submitted["receipt"]["status"],
            "submit_agent_seconds": submitted["seconds"],
            "chat_stop": stopped,
            "ready": ready,
        },
    )


def test_real_v1_rollback_upload_shutdown_and_v2_history(live_documents):
    live = live_documents
    historical = json.loads((live.out / "reader-images-v2.json").read_text())
    history = live.state(historical["thread_id"], headers=live.reader)["values"][
        "messages"
    ]
    before = live.counts()
    try:
        live.configure(1, False)
        path = f"/api/projects/{live.projects['alpha']}/knowledge/"
        capabilities = live.request("GET", path + "capabilities", headers=live.reader)
        assert capabilities["read_enabled"] and not capabilities["upload_enabled"]
        assert capabilities["disabled_reason"] == "knowledge_upload_disabled"
        documents = live.request("GET", path + "documents", headers=live.reader)
        assert documents["items"]
        receipt = json.loads((live.out / "png.json").read_text())["receipt"]
        assert live.request(
            "GET", path + "jobs/" + receipt["job_id"], headers=live.reader
        )["searchable"]
        assert live.request("GET", path + "jobs", headers=live.reader)["items"]
        result = live.query(
            "reader-v1-rollback",
            "Orion emergency recovery code DR-4826",
            sources_version=1,
        )
        assert all("locator" not in source for source in result["sources"])
        assert (
            live.state(historical["thread_id"], headers=live.reader)["values"][
                "messages"
            ]
            == history
        )
        thread = live.thread()
        run = live.start(
            thread,
            "只尝试使用 mcp_submit_project_knowledge_document；如果工具不可用，明确说明不要改用其他工具，不要提交。",
        )
        assert live.terminal(thread, run)["status"] == "success"
        assert not any(
            m.get("name") == SUBMIT for m in live.state(thread)["values"]["messages"]
        )
        assert live.counts()["jobs"] == before["jobs"]
        live.save(
            "configuration-rollback",
            {
                "v1_query": result,
                "v2_history_unchanged": True,
                "capabilities": capabilities,
                "four_gets_available": True,
                "new_submit_hidden": True,
            },
        )
    finally:
        live.configure(2, True)


def test_real_inflight_dedup_two_projects_read_and_disabled_drain(live_documents):
    live = live_documents
    beta = LiveDocuments()
    beta.projects = {**beta.projects, "alpha": beta.projects["beta"]}
    beta.client.headers["x-project-id"] = beta.projects["alpha"]
    beta.uploader = beta.reader = beta.admin
    agents = beta.request("GET", f"/api/projects/{beta.projects['alpha']}/agents")[
        "items"
    ]
    beta.agents = {
        g: next(a["id"] for a in agents if a["graph_id"] == g)
        for g in ("showcase_demo", "dearflow_agent")
    }
    marker = uuid4().hex[:8]
    raw = f"# Orion queue fixture {marker}\nQueue release inspection code is Q-{marker}. Inspection interval is 26 days.".encode()
    frozen = live.frozen_checksums()
    try:
        with live.pause_next_builder() as monitor:
            first = live.submit("queue-alpha", raw, "text/markdown", "queue-alpha.md")
            assert json.loads(monitor.stdout.readline())["paused"]
            path = f"/api/projects/{live.projects['alpha']}/knowledge/jobs/"
            status = live.request(
                "GET", path + first["receipt"]["job_id"], headers=live.reader
            )
            assert status["status"] == "parsing" and not status["searchable"]
            before = live.counts()
            duplicate = live.submit(
                "queue-alpha-duplicate",
                raw,
                "text/markdown",
                "queue-alpha.md",
                "dearflow_agent",
            )
            assert (
                duplicate["receipt"]["reused"]
                and duplicate["receipt"]["job_id"] == first["receipt"]["job_id"]
            )
            after = live.counts()
            assert before["usage"] == after["usage"] and before["jobs"] == after["jobs"]
            second = beta.submit("queue-beta", raw, "text/markdown", "queue-beta.md")
            assert second["receipt"]["job_id"] != first["receipt"]["job_id"]
            beta_status = beta.request(
                "GET",
                f"/api/projects/{beta.projects['alpha']}/knowledge/jobs/{second['receipt']['job_id']}",
                headers=beta.reader,
            )
            assert beta_status["status"] == "queued" and not beta_status["searchable"]
            old = live.query(
                "reader-during-build",
                "Orion backup retention and restoration drill interval",
            )
            assert any(
                s["document_id"]
                == json.loads((live.out / "old-text.json").read_text())["receipt"][
                    "document_id"
                ]
                for s in old["sources"]
            )
            assert frozen == live.frozen_checksums()
            live.configure(2, False)
            assert not live.request(
                "GET",
                f"/api/projects/{live.projects['alpha']}/knowledge/capabilities",
                headers=live.reader,
            )["upload_enabled"]
        ready_alpha, ready_beta = (
            live.ready(first["receipt"]),
            beta.ready(second["receipt"]),
        )
        assert ready_alpha["searchable"] and ready_beta["searchable"]
        assert frozen == live.frozen_checksums(frozen["namespace"])
        live.save(
            "queue-disabled-drain",
            {
                "alpha_processing": status,
                "beta_queued": beta_status,
                "duplicate": duplicate["receipt"],
                "counts_before_duplicate": before,
                "counts_after_duplicate": after,
                "duplicate_extra_ingestion_events": 0,
                "frozen_snapshot_unchanged": True,
                "old_query_during_build": True,
                "new_upload_disabled": True,
                "ready_alpha": ready_alpha,
                "ready_beta": ready_beta,
            },
        )
    finally:
        beta.client.close()
        live.configure(2, True)


def test_real_frozen_generation_rollback(live_documents):
    live = live_documents
    generations = live.generation_action("inspect")
    old, current = generations["generations"][0], generations["active"]
    frozen = live.frozen_checksums(old)
    latest = live.frozen_checksums(current)
    assert old != current
    before = live.counts()
    try:
        live.configure(2, False)
        live.generation_action("rollback", old)
        path = f"/api/projects/{live.projects['alpha']}/knowledge/"
        visible = live.request("GET", path + "documents", headers=live.reader)
        assert visible["total"] == 1
        png = json.loads((live.out / "png.json").read_text())["receipt"]
        hidden = live.request(
            "GET", path + "jobs/" + png["job_id"], headers=live.reader
        )
        assert hidden["status"] == "ready" and not hidden["searchable"]
        result = live.query("reader-frozen-rollback-v2", "Orion backup retention")
        assert {s["document_id"] for s in result["sources"]} == {
            json.loads((live.out / "old-text.json").read_text())["receipt"][
                "document_id"
            ]
        }
        assert live.counts()["usage"] == before["usage"]
        live.save(
            "generation-rollback",
            {
                "old_version_documents": visible,
                "newer_job_ready_but_hidden": hidden,
                "query_old_version": result,
                "ingestion_usage_unchanged": True,
            },
        )
    finally:
        live.generation_action("rollback", current)
        live.generation_action("enable")
        live.configure(2, True)
    assert frozen == live.frozen_checksums(old)
    assert latest == live.frozen_checksums(current)
    assert live.ready(png)["searchable"]
    restored = live.request("GET", path + "documents", headers=live.reader)
    assert restored["total"] > visible["total"]
    live.save(
        "generation-restore",
        {
            "documents": restored,
            "old_and_current_frozen_bytes_unchanged": True,
            "ingestion_usage_unchanged": live.counts()["usage"] == before["usage"],
        },
    )


def test_real_stop_pending_approval_has_no_late_submit(live_documents):
    live = live_documents
    before = live.counts()
    thread = live.thread()
    raw = b"Pending approval fixture; no admission before user approves."
    ref = live.upload(thread, raw, "text/markdown", "pending-approval.md")
    run = live.start(
        thread,
        "用户明确共享附件。只实际调用一次 mcp_submit_project_knowledge_document，file_ref="
        + json.dumps(ref)
        + "；不要使用其他工具。",
    )
    assert live.terminal(thread, run)["status"] == "interrupted"
    stopped = live.request(
        "POST",
        f"/api/langgraph/threads/{thread}/cancel",
        expected=202,
        headers={**live.uploader, "Idempotency-Key": "pending-stop-" + uuid4().hex},
        json={},
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        value = live.request(
            "GET",
            f"/api/langgraph/threads/{thread}/stop-requests/{stopped['stop_id']}",
            headers=live.uploader,
        )
        if value["phase"] in {"confirmed", "no_active_run"}:
            break
        time.sleep(0.2)
    assert value["phase"] in {"confirmed", "no_active_run"}, value
    assert value["execution_stopped"] is True and value["confirmed_at"] is not None
    first = live.state(thread)
    time.sleep(5)
    later = live.state(thread)
    assert first["values"]["messages"] == later["values"]["messages"]
    assert not any(m.get("name") == SUBMIT for m in later["values"]["messages"])
    assert (
        live.counts()["jobs"] == before["jobs"]
        and live.counts()["usage"] == before["usage"]
    )
    live.save(
        "pending-stop",
        {
            "thread_id": thread,
            "run_id": run,
            "confirmed_stop": value,
            "no_late_submit": True,
            "no_new_ingestion": True,
        },
    )
