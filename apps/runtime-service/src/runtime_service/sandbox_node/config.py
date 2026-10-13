"""Node settings are deployment-owned and never supplied by RPC callers."""

import ipaddress
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from runtime_service.workspace.target import identifier, secret_file


@dataclass(frozen=True)
class NodeConfig:
    node_id: str
    workspaces: Path
    state: Path
    callers: dict
    images: frozenset[str]
    max_active: int = 2
    min_free: int = 5 * 1024**3

    @classmethod
    def load(cls):
        node = identifier(os.environ["SANDBOX_NODE_ID"])
        roots = [
            Path(os.environ[key])
            for key in ("SANDBOX_WORKSPACE_ROOT", "SANDBOX_STATE_ROOT")
        ]
        for root in roots:
            if not root.is_absolute() or any(
                p.is_symlink() for p in (root, *root.parents)
            ):
                raise ValueError("invalid Node storage")
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
        callers = json.loads(secret_file("SANDBOX_AUTH_FILE").read_text())
        if not isinstance(callers, dict) or not callers:
            raise ValueError("caller registry required")
        for host, caller in callers.items():
            identifier(host)
            if set(caller) != {"token_sha256", "certificate_cn", "allowed_ips"}:
                raise ValueError("invalid caller registry")
            if caller["certificate_cn"] != host or not caller["allowed_ips"]:
                raise ValueError("caller must bind a certificate and public source IP")
            if not re.fullmatch(r"[0-9a-f]{64}", caller["token_sha256"]):
                raise ValueError("invalid caller token digest")
            for net in caller["allowed_ips"]:
                if ipaddress.ip_network(net).prefixlen == 0:
                    raise ValueError("caller source IP must be restricted")
        images = frozenset(
            os.environ.get(
                "SANDBOX_ALLOWED_IMAGES", "runtime-agent-workspace:p5,python:3.13-slim"
            ).split(",")
        )
        capacity = int(os.environ.get("SANDBOX_MAX_ACTIVE_CONTAINERS", "2"))
        free = int(os.environ.get("SANDBOX_MIN_FREE_DISK_BYTES", str(5 * 1024**3)))
        if (
            not images
            or any(not item or item.startswith("-") for item in images)
            or not 1 <= capacity <= 2
            or free < 0
        ):
            raise ValueError("invalid Node policy")
        return cls(node, *roots, callers, images, capacity, free)
