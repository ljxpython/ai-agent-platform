"""Only the local Engine socket, approved mounts and bounded owned resources."""

import json
import os
import selectors
import shutil
import subprocess
import time

from runtime_service.workspace.docker_policy import MAX_OUTPUT, docker_workspace_args
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.path_patterns import replace_output_path_matches


class Engine:
    def __init__(self, config, ledger, storage, locks):
        self.config, self.ledger, self.storage, self.locks = (
            config,
            ledger,
            storage,
            locks,
        )
        self.processes = {}
        self.docker = shutil.which("docker") or "/usr/bin/docker"
        self.image_ids = {}

    def environment(self):
        return {
            "PATH": os.defpath,
            "HOME": str(self.config.state),
            "DOCKER_CONFIG": str(self.config.state / "docker-client"),
        }

    def argv(self, *args):
        return [self.docker, "--host=unix:///var/run/docker.sock", *args]

    def control(self, *args, seconds=12, limit=65536):
        try:
            process = subprocess.Popen(
                self.argv(*args),
                env=self.environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            output = bytearray()
            deadline = time.monotonic() + seconds
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(process.args, seconds)
                    for key, _ in selector.select(min(remaining, 0.2)):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fd)
                        else:
                            if len(output) + len(chunk) > limit:
                                raise ValueError("docker output limit")
                            output.extend(chunk)
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
            return process.returncode, bytes(output)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            raise DocumentError("sandbox_control_unavailable", 503) from None
        finally:
            if "process" in locals():
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
                process.stdout.close()

    def readiness(self):
        code, data = self.control("info", "--format={{.ServerVersion}}")
        if code or not data.strip():
            raise DocumentError("sandbox_control_unavailable", 503)
        for image in self.config.images:
            code, data = self.control("image", "inspect", image, "--format={{.Id}}")
            if code or not data.strip():
                raise DocumentError("sandbox_image_unavailable", 503)
            self.image_ids[image] = data.decode().strip()
        return data

    def reserve(self, request, kind, image, seconds, skills=None):
        if image not in self.config.images:
            raise DocumentError("runtime.workspace.image_invalid", 400)
        if shutil.disk_usage(self.config.workspaces).free < self.config.min_free:
            raise DocumentError("sandbox_disk_capacity_reached", 429)
        with self.locks.hold(self.storage.key(request)):
            root = self.storage.check(request)
            return self._reserve(request, kind, image, seconds, skills, root)

    def _reserve(self, request, kind, image, seconds, skills, root):
        if os.getuid() == 0:
            raise DocumentError("sandbox_nonroot_required", 503)
        policy = {
            "root": str(root),
            "protected": request.graph == "dearflow_agent"
            or request.arguments.get("protected", False),
            "skills": skills,
            "uid": os.getuid(),
            "gid": os.getgid(),
            "image_id": self.image_ids.get(image),
        }
        from runtime_service.sandbox_node.ledger import digest

        name = (
            "runtime-node-"
            + digest([request.execution_host, request.operation_id])[:40]
        )
        row = {
            "host": request.execution_host,
            "id": request.operation_id,
            "workspace": self.storage.key(request),
            "kind": kind,
            "name": name,
            "image": image,
            "policy": json.dumps(policy),
            "deadline": time.time() + seconds + 15,
        }
        self.ledger.reserve(row, self.config.max_active)
        return row

    def create_args(self, row):
        policy = json.loads(row["policy"])
        from pathlib import Path

        root = Path(policy["root"])
        skills = (
            self.storage.snapshot_path(root, policy["skills"])
            if policy["skills"]
            else None
        )
        args = docker_workspace_args(
            root,
            image=row["image"],
            name=row["name"],
            skills=skills,
            protected=policy["protected"],
            background=True,
        )
        return [
            *args[2:-1],
            "--restart=no",
            "--log-driver=local",
            "--log-opt=max-size=2m",
            "--log-opt=max-file=2",
            "--label=runtime.sandbox.node=" + self.config.node_id,
            "--label=runtime.sandbox.host=" + row["host"],
            "--label=runtime.sandbox.resource=" + row["id"],
            "--label=runtime.sandbox.workspace=" + row["workspace"],
            row["image"],
        ]

    def inspect(self, row):
        code, data = self.control(
            "inspect", "--type=container", "--format={{json .}}", row["name"]
        )
        if code:
            code, data = self.control("info", "--format={{.ServerVersion}}")
            if code or not data.strip():
                raise DocumentError("sandbox_control_unavailable", 503)
            return None
        try:
            return self.inspect_facts(row, json.loads(data))
        except (ValueError, KeyError, TypeError):
            raise DocumentError("sandbox_resource_policy_mismatch", 409) from None

    def inspect_facts(self, row, facts):
        expected = {
            "runtime.sandbox.node": self.config.node_id,
            "runtime.sandbox.host": row["host"],
            "runtime.sandbox.resource": row["id"],
            "runtime.sandbox.workspace": row["workspace"],
        }
        policy = json.loads(row["policy"])
        config, host = facts["Config"], facts["HostConfig"]
        mounts = {item["Destination"]: item for item in facts["Mounts"]}
        correct = (
            all(config["Labels"].get(k) == v for k, v in expected.items())
            and config["Image"] == row["image"]
            and (not policy.get("image_id") or facts["Image"] == policy["image_id"])
            and host["NetworkMode"] == "none"
            and host["ReadonlyRootfs"]
            and not host["Privileged"]
            and "ALL" in (host["CapDrop"] or [])
            and not host["CapAdd"]
            and host["SecurityOpt"] == ["no-new-privileges"]
            and host.get("Tmpfs") == {"/tmp": "rw,nosuid,nodev,size=16777216"}
            and host.get("Ulimits")
            == [{"Name": "fsize", "Soft": 8388608, "Hard": 8388608}]
            and config["User"] == f"{policy['uid']}:{policy['gid']}"
            and host["Memory"] == 256 * 1024**2
            and host["PidsLimit"] == 64
            and host["NanoCpus"] == 1_000_000_000
            and not host["PortBindings"]
            and not host.get("Devices")
            and host.get("RestartPolicy", {}).get("Name") in {"no", ""}
            and host.get("LogConfig")
            == {"Type": "local", "Config": {"max-size": "2m", "max-file": "2"}}
            and mounts["/workspace"]["Source"] == policy["root"]
            and mounts["/workspace"]["RW"] == (not policy["protected"])
        )
        allowed = {"/workspace", "/tmp"}
        if policy["protected"]:
            allowed.add("/workspace/work")
            correct &= (
                mounts["/workspace/work"]["Source"] == policy["root"] + "/work"
                and mounts["/workspace/work"]["RW"]
            )
        if policy["skills"]:
            allowed.add("/skills")
            correct &= (
                mounts["/skills"]["Source"]
                == str(
                    self.storage.snapshot_path(
                        __import__("pathlib").Path(policy["root"]), policy["skills"]
                    )
                )
                and not mounts["/skills"]["RW"]
            )
        if not correct or set(mounts) - allowed:
            raise DocumentError("sandbox_resource_policy_mismatch", 409)
        return {"id": facts["Id"], **facts["State"]}

    def remove(self, row, *, stop=False):
        state = self.inspect(row)
        if state is None:
            self.ledger.update(row["host"], row["id"], "removed")
            return True
        if state["Running"] and not stop:
            return False
        code, _ = self.control("rm", *(["-f"] if stop else []), row["name"])
        confirmed = code == 0 and self.inspect(row) is None
        self.ledger.update(
            row["host"], row["id"], "removed" if confirmed else "unconfirmed"
        )
        return confirmed

    def execute(self, request, arguments):
        command, seconds = arguments["command"], arguments.get("timeout", 30)
        if (
            not isinstance(command, str)
            or not command.strip()
            or len(command) > 32768
            or type(seconds) is not int
            or not 1 <= seconds <= 60
        ):
            raise DocumentError("sandbox_execute_invalid")
        row = self.reserve(
            request, "execute", arguments["image"], seconds, arguments.get("skills")
        )
        loader = (
            'timeout -s KILL "$1" sh -c "$2" > /tmp/output 2>&1; result=$?; '
            + f'head -c {MAX_OUTPUT} /tmp/output; exit "$result"'
        )
        with self.locks.hold((row["host"], row["id"])):
            if (
                self.ledger.resource(row["host"], row["id"], row["workspace"])["status"]
                == "removed"
            ):
                raise DocumentError("sandbox_resource_cancelled", 409)
            code, _ = self.control(
                "create",
                *self.create_args(row),
                "sh",
                "-c",
                loader,
                "runtime",
                str(seconds),
                command,
            )
            if code:
                self.ledger.update(row["host"], row["id"], "unconfirmed")
                raise DocumentError("runtime.workspace.execution_outcome_unknown", 409)
            self.inspect(row)
            process = subprocess.Popen(
                self.argv("start", "-a", row["name"]),
                env=self.environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self.processes[(row["host"], row["id"])] = process
            self.ledger.update(row["host"], row["id"], "running")
        confirmed = False
        try:
            output, _ = process.communicate(timeout=seconds + 15)
            state = self.inspect(row)
            if state is None or state["Running"]:
                raise DocumentError("runtime.workspace.execution_outcome_unknown", 409)
            result = {
                "output": output[:MAX_OUTPUT].decode("utf-8", errors="replace"),
                "exit_code": state["ExitCode"],
                "truncated": len(output) >= MAX_OUTPUT,
            }
            result["output"] = replace_output_path_matches(
                result["output"], json.loads(row["policy"])["root"], "/workspace"
            )
            return result
        except subprocess.TimeoutExpired:
            raise DocumentError(
                "runtime.workspace.execution_outcome_unknown", 409
            ) from None
        finally:
            with self.locks.hold((row["host"], row["id"])):
                if process.poll() is None:
                    process.kill()
                process.communicate()
                self.processes.pop((row["host"], row["id"]), None)
                confirmed = self.remove(row, stop=True)
            if "result" in locals():
                result["cleanup_confirmed"] = confirmed

    def cancel(self, request, resource_id):
        with self.locks.hold((request.execution_host, resource_id)):
            self.ledger.cancellation(
                request.execution_host, resource_id, self.storage.key(request)
            )
            try:
                row = self.ledger.resource(
                    request.execution_host, resource_id, self.storage.key(request)
                )
            except DocumentError as exc:
                if exc.status_code == 404:
                    return {"confirmed": True}
                raise
            return {"confirmed": self.remove(row, stop=True)}

    def reconcile(self, *, startup=False):
        rows = self.ledger.resources()
        code, data = self.control(
            "ps",
            "-a",
            "--filter=label=runtime.sandbox.node=" + self.config.node_id,
            "--format={{.Names}}",
            limit=256 * 1024,
        )
        if code:
            raise DocumentError("sandbox_control_unavailable", 503)
        known = {row["name"] for row in rows if row["status"] != "removed"}
        if set(data.decode().splitlines()) - known:
            raise DocumentError("sandbox_unregistered_resource", 409)
        for row in rows:
            if row["status"] == "removed":
                continue
            with self.locks.hold((row["host"], row["id"])):
                state = self.inspect(row)
                if state is None:
                    self.ledger.update(row["host"], row["id"], "removed")
                elif (
                    startup
                    and row["kind"] == "terminal"
                    or time.time() >= row["deadline"]
                ):
                    if row["kind"] == "background":
                        if state["Running"]:
                            self.control("kill", row["name"])
                        self.ledger.update(row["host"], row["id"], "exited")
                    else:
                        self.remove(row, stop=True)
                elif not state["Running"] and state["Status"] != "created":
                    self.ledger.update(row["host"], row["id"], "exited")
