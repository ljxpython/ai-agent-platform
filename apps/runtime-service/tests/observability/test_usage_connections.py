import pytest
from psycopg_pool import PoolTimeout

from runtime_service.db import usage_connections as module


@pytest.fixture
def pools(monkeypatch):
    created = []

    class Pool:
        closed = False

        def __init__(self, dsn, **kwargs):
            self.dsn = dsn
            created.append(self)

        def wait(self, **kwargs):
            if self.dsn == "unavailable":
                raise PoolTimeout("test database unavailable")

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "_pool", None)
    monkeypatch.setattr(module, "_dsn", None)
    monkeypatch.setattr(module, "ConnectionPool", Pool)
    monkeypatch.setenv("DATABASE_URI", "first")
    yield created
    module.close_query_pool()


def test_pool_is_reused_and_dsn_switch_closes_old_pool(pools, monkeypatch):
    reads = module.query_pool()
    assert module.query_pool() is reads
    monkeypatch.setenv("DATABASE_URI", "second")
    assert module.query_pool() is not reads and reads.closed
    module.close_query_pool()
    assert all(pool.closed for pool in pools)


def test_failed_cold_pool_is_closed_and_a_later_request_can_recover(pools, monkeypatch):
    monkeypatch.setenv("DATABASE_URI", "unavailable")
    with pytest.raises(PoolTimeout):
        module.query_pool()
    assert pools[-1].closed
    monkeypatch.setenv("DATABASE_URI", "recovered")
    assert module.query_pool().dsn == "recovered"
