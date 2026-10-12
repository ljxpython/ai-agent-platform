"""A bounded connection pool reserved for read-only usage analytics."""

import atexit
import threading

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from runtime_service.db import normalize_dsn

_lock = threading.Lock()
_pool = None
_dsn = None


def query_pool():
    global _pool, _dsn
    dsn = normalize_dsn()
    with _lock:
        if _pool is not None and _dsn == dsn:
            return _pool
        if _pool is not None:
            _pool.close()
            _pool = _dsn = None
        pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=1,
            timeout=0.1,
            open=True,
            kwargs=dict(
                row_factory=dict_row,
                autocommit=True,
                prepare_threshold=0,
                connect_timeout=1,
                options="-c statement_timeout=1000 -c lock_timeout=250 -c timezone=UTC -c max_parallel_workers_per_gather=0",
            ),
        )
        try:
            pool.wait(timeout=1)
        except Exception:
            pool.close()
            raise
        _pool, _dsn = pool, dsn
        return _pool


def close_query_pool():
    global _pool, _dsn
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool = _dsn = None


atexit.register(close_query_pool)
