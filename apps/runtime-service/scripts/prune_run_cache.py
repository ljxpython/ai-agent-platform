"""Remove expired, terminal Redis replay caches; never delete durable PG data.

Default is a dry run. Use --apply only after reviewing the inventory.
"""

import argparse
import json
import os
import time
from pathlib import Path
from uuid import UUID

import psycopg
import redis
from dotenv import dotenv_values

TERMINAL = {"success", "error", "timeout", "cancelled", "canceled"}


def cache_identity(key: str, prefix: str):
    if not key.startswith(f"{prefix}:run-stream:"):
        return None
    parts = key[len(prefix) + len(":run-stream:") :].split(":")
    if len(parts) != 2:
        return None
    try:
        return UUID(parts[0]), UUID(parts[1])
    except ValueError:
        return None


def expired_terminal(row, retention_seconds: int) -> bool:
    return bool(row and row[0] in TERMINAL and row[1] >= retention_seconds)


def prune(pg, cache, prefix: str, retention_seconds: int, apply: bool):
    counts = {"deleted": 0, "eligible": 0, "retained": 0, "unknown": 0}
    estimated_bytes = 0
    for key in cache.scan_iter(match=f"{prefix}:run-stream:*", count=50):
        identity = cache_identity(key.decode(), prefix)
        if identity is None:
            counts["unknown"] += 1
            continue
        thread_id, run_id = identity
        # Lock only this run until UNLINK completes: a concurrent status change
        # cannot turn a reviewed terminal cache into an active deletion target.
        with pg.transaction():
            row = pg.execute(
                "SELECT status, EXTRACT(EPOCH FROM (now() - updated_at)) "
                "FROM runs WHERE thread_id = %s AND run_id = %s FOR SHARE",
                (thread_id, run_id),
            ).fetchone()
            if not row:
                counts["unknown"] += 1
                continue
            if not expired_terminal(row, retention_seconds):
                counts["retained"] += 1
                continue
            counts["eligible"] += 1
            estimated_bytes += cache.memory_usage(key, samples=1) or 0
            if apply:
                counts["deleted"] += cache.unlink(key)
        # Allow the server's lazy-free thread and current users to make progress.
        time.sleep(0.01)
    return {**counts, "estimated_bytes": estimated_bytes, "applied": apply}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--retention-seconds", type=int, default=3600)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.retention_seconds < 3600:
        parser.error("retention must be at least 3600 seconds")
    env = {**dotenv_values(args.env_file), **os.environ}
    prefix = env.get("GRAPHHARBOR_REDIS_PREFIX", "graphharbor:runtime").strip(":")
    if not prefix or any(c in prefix for c in "*?[]"):
        parser.error("Redis prefix must be literal and non-empty")
    with (
        psycopg.connect(env["DATABASE_URI"], autocommit=True) as pg,
        redis.Redis.from_url(env["REDIS_URI"], socket_timeout=5) as cache,
    ):
        print(json.dumps(prune(pg, cache, prefix, args.retention_seconds, args.apply)))


if __name__ == "__main__":
    main()
