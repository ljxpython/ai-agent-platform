"""One process owns admission, operations, PTYs and recovery facts."""

import asyncio
import fcntl
import hashlib
import hmac
import ipaddress
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.tools import ToolException
from pydantic import ValidationError

from runtime_service.errors import RuntimeWorkspaceError
from runtime_service.sandbox_node.config import NodeConfig
from runtime_service.sandbox_node.engine import Engine
from runtime_service.sandbox_node.ledger import Ledger
from runtime_service.sandbox_node.protocol import (
    READ_OPERATIONS,
    Rpc,
    validate_arguments,
)
from runtime_service.sandbox_node.storage import Storage
from runtime_service.workspace.acquire_serialization import AcquireSerializer
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.browser import WorkspaceBrowser
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
from runtime_service.workspace.image_io import ImageWorkspace
from runtime_service.workspace.node_client import MAX_MESSAGE, decode, encode


class Node:
    def __init__(self, config):
        self.config = config
        self.ledger = Ledger(config.state / "node.sqlite3")
        self.locks = AcquireSerializer(max_workers=4)
        self.storage = Storage(config, self.ledger)
        self.engine = Engine(config, self.ledger, self.storage, self.locks)
        from runtime_service.sandbox_node.terminal import NodeTerminals

        self.terminals = NodeTerminals(self)
        self.ready = False

    def authenticate(self, request):
        host = request.headers.get("x-execution-host", "")
        caller = self.config.callers.get(host)
        certificate = request.scope.get("sandbox_client_certificate", {})
        names = [
            value
            for group in certificate.get("subject", ())
            for key, value in group
            if key == "commonName"
        ]
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        address = ipaddress.ip_address(request.client.host)
        allowed = caller and any(
            address in ipaddress.ip_network(net) for net in caller["allowed_ips"]
        )
        if (
            request.scope["scheme"] != "https"
            or not caller
            or names != [caller["certificate_cn"]]
            or not allowed
            or request.headers.get("x-sandbox-node") != self.config.node_id
            or not hmac.compare_digest(
                hashlib.sha256(token.encode()).hexdigest(), caller["token_sha256"]
            )
        ):
            raise DocumentError("sandbox_caller_denied", 403)
        return host

    def perform(self, request):
        operation = request.operation
        if operation.startswith("terminal."):
            return self.terminals.handle(
                request, operation.split(".")[1], decode(request.arguments)
            )
        if operation.startswith("background."):
            from runtime_service.sandbox_node.background import handle_background

            return handle_background(self, request)
        if operation in {"execute", "cancel"}:
            if operation == "execute":
                return self.engine.execute(request, request.arguments)
            return self.engine.cancel(request, request.arguments["resource_id"])
        if operation == "fork":
            source = self.storage.fork_source(
                request, request.arguments["source_scope"]
            )
            with ExitStack() as stack:
                for key in sorted(
                    {self.storage.key(source), self.storage.key(request)}
                ):
                    stack.enter_context(self.locks.hold(key))
                return self.storage.fork(request, source)
        with self.locks.hold(self.storage.key(request)):
            return self.files(request)

    def files(self, request):
        operation, args = request.operation, decode(request.arguments)
        if operation.startswith("cleanup."):
            from runtime_service.sandbox_node.cleanup import handle_cleanup

            return handle_cleanup(self, request)
        if operation == "prepare":
            return self.storage.prepare(request, args.get("examples", {}))
        if operation == "is_prepared":
            try:
                self.storage.check(request)
                return {"prepared": True}
            except DocumentError:
                return {"prepared": False}
        if operation == "operation":
            return self.ledger.operation(
                request.execution_host, args["resource_id"], self.storage.key(request)
            )
        if operation == "discover":
            return [
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "status": row["status"],
                    "deadline": row["deadline"],
                }
                for row in self.ledger.resources(
                    request.execution_host, self.storage.key(request)
                )
            ]
        if operation == "publish_skills":
            return self.storage.publish_skills(request, **args)
        if operation == "restore_skills":
            return self.storage.restore_skills(request, **args)
        if operation in {"image.put_upload", "document.put"}:
            self.storage.prepare(request, {})
        root = self.storage.check(request)
        if operation in {
            "image.put_upload",
            "image.save_asset",
            "document.put",
            "artifact.publish",
        }:
            self.storage.quota(
                root, "/workspace/work/.capacity-check", len(args.get("data", b""))
            )
        if operation == "research_evidence":
            return self.storage.research(root, args)
        if operation == "upload_files":
            results = []
            if (
                len(args["files"]) > 64
                or sum(len(content) for _, content in args["files"]) > 20 * 1024**2
            ):
                raise DocumentError("sandbox_request_too_large", 413)
            for path, content in args["files"]:
                result = (
                    self.storage.mutate(root, "write", {"path": path, "content": ""})
                    if not path.startswith(
                        "/workspace/work/"
                        if request.graph == "dearflow_agent"
                        else "/workspace/"
                    )
                    else self.storage.write_bytes(root, path, content)
                )
                results.append({"path": path, "error": result.get("error")})
            return results
        skills = args.pop("skills", None)
        if skills:
            if operation not in {
                "ls",
                "read",
                "read_raw",
                "glob",
                "grep",
                "download_files",
            }:
                raise DocumentError("skill_resource_read_only", 403)
            snapshot = self.storage.snapshot_path(root, skills)
            from runtime_service.sandbox_node.skills import skills_operation

            return skills_operation(snapshot, operation, args)
        if operation == "download_files":
            results = []
            if len(args["paths"]) > 64:
                raise DocumentError("sandbox_request_too_large", 413)
            total = 0
            for path in args["paths"]:
                try:
                    content = self.storage.read_bytes(root, path)
                    total += len(content)
                    if total > 20 * 1024**2:
                        raise DocumentError("sandbox_response_too_large", 413)
                    results.append({"path": path, "content": content})
                except DocumentError as exc:
                    if exc.code == "sandbox_response_too_large":
                        raise
                    error = (
                        "file_not_found"
                        if exc.code == "file_not_found"
                        else "permission_denied"
                        if exc.code
                        in {"file_permission_denied", "invalid_workspace_path"}
                        else "invalid_path"
                    )
                    results.append({"path": path, "error": error})
            return results
        handlers = {
            "ls": lambda path: self.storage.ls(root, path.rstrip("/") or "/workspace"),
            "read": lambda **kw: self.storage.read(root, kw),
            "read_raw": lambda path: self.storage.file_data(root, path),
            "glob": lambda **kw: self.storage.search(root, kw, grep=False),
            "grep": lambda **kw: self.storage.search(root, kw, grep=True),
            "write": lambda **kw: self.storage.mutate(
                root, "write", kw, protected=request.graph == "dearflow_agent"
            ),
            "edit": lambda **kw: self.storage.mutate(
                root, "edit", kw, protected=request.graph == "dearflow_agent"
            ),
            "delete": lambda **kw: self.storage.mutate(
                root, "delete", kw, protected=request.graph == "dearflow_agent"
            ),
            "image.read": ImageWorkspace(root).read,
            "image.read_asset": ImageWorkspace(root).read_asset,
            "image.put_upload": ImageWorkspace(root).put_upload,
            "image.save_asset": ImageWorkspace(root).save_asset,
            "document.put": DocumentWorkspace(root).put,
            "document.read": DocumentWorkspace(root).read,
            "artifact.publish": ArtifactWorkspace(root).publish,
            "artifact.read": ArtifactWorkspace(root).read,
            "artifact.list": ArtifactWorkspace(root).list_artifacts,
            "browser.list": WorkspaceBrowser(root).list_directory,
            "browser.read": WorkspaceBrowser(root).read_file,
            "browser.preview": WorkspaceBrowser(root).preview,
            "browser.archive": lambda: self.storage.archive(root),
        }
        if operation not in handlers:
            raise DocumentError("sandbox_operation_invalid")
        return handlers[operation](**args)

    def rpc(self, request):
        validate_arguments(request)
        if request.node_id != self.config.node_id:
            raise DocumentError("sandbox_node_mismatch", 403)
        if not self.ready and request.operation not in READ_OPERATIONS | {
            "cancel",
            "background.stop",
            "background.remove",
            "terminal.close",
        }:
            if (
                self.ledger.operation(
                    request.execution_host,
                    request.operation_id,
                    self.storage.key(request),
                )["status"]
                == "missing"
            ):
                raise DocumentError("sandbox_not_ready", 503)
        if request.operation in READ_OPERATIONS:
            return self.perform(request)
        row, fresh = self.ledger.begin(
            request.execution_host,
            request.operation_id,
            self.storage.key(request),
            request.model_dump(),
        )
        if not fresh:
            if row["status"] == "rejected":
                error = json.loads(row["result"])
                raise DocumentError(error["code"], error["status_code"])
            if row["status"] != "finished":
                raise DocumentError("runtime.workspace.execution_outcome_unknown", 409)
            return decode(json.loads(row["result"]))
        try:
            result = self.perform(request)
        except DocumentError as exc:
            if exc.code in {
                "sandbox_capacity_reached",
                "sandbox_disk_capacity_reached",
                "sandbox_resource_cancelled",
                "runtime.workspace.image_invalid",
                "sandbox_execute_invalid",
                "sandbox_operation_invalid",
                "sandbox_receipt_ack_required",
                "workspace_cleanup_protected",
                "workspace_cleanup_evidence_invalid",
                "workspace_cleanup_policy_invalid",
                "workspace_cleanup_unsupported",
                "terminal_not_found",
                "terminal_instance_changed",
                "terminal_input_conflict",
                "terminal_input_sequence",
                "terminal_exited",
                "terminal_input_busy",
            }:
                self.ledger.reject(request.execution_host, request.operation_id, exc)
            raise
        self.ledger.finish(request.execution_host, request.operation_id, result)
        return result


def create_app(config=None):
    node = Node(config or NodeConfig.load())
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sandbox-node")
    janitor = None
    process_lock = None

    async def sweep():
        while True:
            await asyncio.sleep(5)
            try:
                await asyncio.get_running_loop().run_in_executor(
                    executor, node.engine.reconcile
                )
                if not node.ready:
                    await asyncio.get_running_loop().run_in_executor(
                        executor, node.engine.readiness
                    )
                    node.ready = True
            except Exception:
                node.ready = False
                logging.getLogger(__name__).warning(
                    "Sandbox readiness unavailable; admission closed"
                )

    @asynccontextmanager
    async def lifespan(app):
        nonlocal janitor, process_lock
        process_lock = (node.config.state / "manager.lock").open("a")
        try:
            fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            await asyncio.to_thread(node.engine.readiness)
            await asyncio.to_thread(node.engine.reconcile, startup=True)
            node.ready = True
            janitor = asyncio.create_task(sweep())
            yield
        finally:
            node.ready = False
            if janitor:
                janitor.cancel()
                await asyncio.gather(janitor, return_exceptions=True)
            await asyncio.to_thread(node.terminals.shutdown)
            # Uvicorn has drained HTTP; finish bounded in-flight workers before closing locks.
            await asyncio.to_thread(executor.shutdown, wait=True, cancel_futures=True)
            node.locks.close()
            process_lock.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.node = node

    @app.exception_handler(DocumentError)
    async def document_error(request, error):
        return JSONResponse(
            {"error": {"code": error.code}}, status_code=error.status_code
        )

    @app.exception_handler(RuntimeWorkspaceError)
    async def workspace_error(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=409)

    @app.get("/v1/ready")
    async def ready(request: Request):
        node.authenticate(request)
        return JSONResponse(
            {"ready": node.ready, "version": 1, "node_id": node.config.node_id},
            status_code=200 if node.ready else 503,
        )

    @app.post("/v1/rpc")
    async def rpc(request: Request):
        host = node.authenticate(request)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_MESSAGE:
                raise DocumentError("sandbox_request_too_large", 413)
            body.extend(chunk)
        try:
            payload = Rpc.model_validate_json(body)
            if payload.execution_host != host:
                raise DocumentError("sandbox_caller_denied", 403)
            result = await asyncio.get_running_loop().run_in_executor(
                executor, node.rpc, payload
            )
            return {"result": encode(result)}
        except (ValidationError, TypeError, KeyError, ValueError, RecursionError):
            raise DocumentError("sandbox_request_invalid") from None
        except DocumentError:
            raise
        except ToolException as error:
            from runtime_service.workspace.image_io import ImageWorkspaceError

            if isinstance(error, ImageWorkspaceError):
                raise DocumentError(error.code, error.status_code) from None
            raise DocumentError("workspace_file_unavailable", 404) from None

    return app
