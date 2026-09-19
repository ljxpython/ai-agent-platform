"""Dear-owned PostgreSQL connections and explicit schema deployment."""
from __future__ import annotations

import json

from runtime_service.db import connect


def lock_scope(db, scope: tuple[str, str, str], resource: str):
    if len(scope) != 3 or any(not isinstance(x, str) or not x or len(x) > 200 for x in scope):
        raise ValueError("invalid_governance_scope")
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
               (json.dumps([resource, *scope]),))


if __name__ == "__main__":
    from runtime_service.db import upgrade
    upgrade()
