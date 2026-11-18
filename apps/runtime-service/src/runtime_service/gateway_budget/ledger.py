"""Transactional projections derived only from Runtime model-call facts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb

from runtime_service.db.repositories.usage import _connection


def locked(conn, tenant):
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 81019))", (tenant,))


def window(unit, at):
    at = at.astimezone(UTC)
    start = at.replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "DAYS":
        end = start + timedelta(days=1)
    elif unit == "WEEKS":
        start -= timedelta(days=(start.weekday() + 1) % 7)
        end = start + timedelta(days=7)
    elif unit == "MONTHS":
        start = start.replace(day=1)
        end = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
    else:
        raise ValueError("invalid_budget_period")
    return start, end


def utc(value):
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )


def key(row):
    return (
        row["tenant_id"],
        row["policy_id"],
        row["definition_version"],
        row["window_start"],
    )


def event(conn, row):
    policy = row["policy"]
    if row["known_spend"] < Decimal(policy["budget_amount"]):
        return
    event_id = str(
        uuid5(NAMESPACE_URL, "gateway-budget:" + ":".join(map(str, key(row))))
    )
    payload = {
        "event_id": event_id,
        "tenant_id": row["tenant_id"],
        "policy": policy,
        "window_start": row["window_start"].isoformat(),
        "window_end": row["window_end"].isoformat(),
        "known_spend": format(row["known_spend"], ".12f"),
    }
    conn.execute(
        "INSERT INTO runtime_budget_outbox "
        "(event_id,tenant_id,policy_id,definition_version,window_start,payload) "
        "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (event_id, *key(row), Jsonb(payload)),
    )


def _ensure(conn, tenant, policy, at):
    start, end = window(policy["duration"]["unit"], at)
    if end <= utc(policy["definition_started_at"]):
        return None
    stop = utc(policy["deleted_at"]) if policy.get("deleted_at") else None
    if stop is not None and start >= stop:
        return None
    identity = (tenant, policy["id"], policy["definition_version"], start)
    inserted = conn.execute(
        "INSERT INTO runtime_budget_windows "
        "(tenant_id,policy_id,definition_version,window_start,window_end,valid_until,policy) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING policy_id",
        (*identity, end, stop, Jsonb(policy)),
    ).fetchone()
    if inserted:
        # Same tenant fence as every usage writer: committed-before or updated-after.
        conn.execute(
            "INSERT INTO runtime_usage_runs "
            "(tenant_id,project_id,run_id,thread_id,graph_id,collection_started_at,collection_ended_at,degraded) "
            "SELECT %s,r.kwargs#>>'{__graphharbor_runtime_context,auth_user,project_id}',"
            "r.run_id,COALESCE(r.thread_id,r.run_id),'budget_coverage_gap',r.created_at,r.updated_at,true "
            "FROM runs r WHERE r.status NOT IN ('pending','running') AND r.created_at < %s AND r.updated_at >= %s "
            "AND r.kwargs#>>'{__graphharbor_runtime_context,auth_user,tenant_id}'=%s "
            "AND r.kwargs#>>'{__graphharbor_runtime_context,auth_user,project_id}' IS NOT NULL "
            "AND (%s::text IS NULL OR r.kwargs#>>'{__graphharbor_runtime_context,auth_user,project_id}'=%s) "
            "AND NOT EXISTS(SELECT 1 FROM runtime_usage_runs u WHERE u.tenant_id=%s "
            "AND u.project_id=r.kwargs#>>'{__graphharbor_runtime_context,auth_user,project_id}' AND u.run_id=r.run_id) "
            "ON CONFLICT(tenant_id,project_id,run_id) DO NOTHING",
            (
                tenant,
                end,
                start,
                tenant,
                policy.get("project_id"),
                policy.get("project_id"),
                tenant,
            ),
        )
        rebuild(conn, identity)
    return conn.execute(
        "SELECT * FROM runtime_budget_windows WHERE "
        "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s)",
        identity,
    ).fetchone()


def rebuild(conn, identity):
    row = conn.execute(
        "SELECT * FROM runtime_budget_windows WHERE "
        "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s)",
        identity,
    ).fetchone()
    policy = row["policy"]
    conn.execute(
        "INSERT INTO runtime_budget_contributions "
        "(tenant_id,policy_id,definition_version,window_start,project_id,run_id,model_call_id,amount,pending) "
        "SELECT %s,%s,%s,%s,c.project_id,c.run_id,c.model_call_id,c.estimated_cost_usd,c.outcome='started' "
        "FROM runtime_usage_calls c WHERE c.tenant_id=%s AND c.started_at >= %s AND c.started_at < %s "
        "AND (%s::text IS NULL OR c.project_id=%s) "
        "AND (%s::timestamptz IS NULL OR c.started_at < %s) "
        "ON CONFLICT(tenant_id,policy_id,definition_version,window_start,project_id,run_id,model_call_id) "
        "DO UPDATE SET amount=EXCLUDED.amount,pending=EXCLUDED.pending",
        (
            *identity,
            row["tenant_id"],
            row["window_start"],
            row["window_end"],
            policy.get("project_id"),
            policy.get("project_id"),
            row["valid_until"],
            row["valid_until"],
        ),
    )
    row = conn.execute(
        "UPDATE runtime_budget_windows SET known_spend=(SELECT COALESCE(sum(amount),0) "
        "FROM runtime_budget_contributions WHERE "
        "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s)) WHERE "
        "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s) RETURNING *",
        (*identity, *identity),
    ).fetchone()
    event(conn, row)


def apply_snapshot(conn, snapshot, at, project_id=None):
    tenant, revision = snapshot["tenant_id"], snapshot["revision"]
    old = conn.execute(
        "SELECT * FROM runtime_budget_tenants WHERE tenant_id=%s", (tenant,)
    ).fetchone()
    if old and old["revision"] > revision:
        return False
    if old and old["revision"] == revision and old["snapshot"] != snapshot:
        raise ValueError("budget_revision_conflict")
    if not old or old["revision"] < revision:
        prior = {p["id"]: p for p in old["snapshot"]["policies"]} if old else {}
        for policy in snapshot["policies"]:
            previous = prior.get(policy["id"])
            if previous and (
                previous["definition_version"] != policy["definition_version"]
                or policy.get("deleted_at")
            ):
                conn.execute(
                    "UPDATE runtime_budget_windows SET valid_until=COALESCE(valid_until,%s) "
                    "WHERE tenant_id=%s AND policy_id=%s AND definition_version=%s",
                    (
                        utc(policy.get("deleted_at") or policy["updated_at"]),
                        tenant,
                        policy["id"],
                        previous["definition_version"],
                    ),
                )
            if (
                previous
                and previous["definition_version"] == policy["definition_version"]
            ):
                conn.execute(
                    "UPDATE runtime_budget_windows SET policy=%s WHERE tenant_id=%s AND policy_id=%s "
                    "AND definition_version=%s AND window_end > %s",
                    (
                        Jsonb(policy),
                        tenant,
                        policy["id"],
                        policy["definition_version"],
                        utc(policy["updated_at"]),
                    ),
                )
        conn.execute(
            "INSERT INTO runtime_budget_tenants(tenant_id,revision,snapshot) VALUES(%s,%s,%s) "
            "ON CONFLICT(tenant_id) DO UPDATE SET revision=EXCLUDED.revision,snapshot=EXCLUDED.snapshot",
            (tenant, revision, Jsonb(snapshot)),
        )
    for policy in snapshot["policies"]:
        if not policy.get("deleted_at") and (
            project_id is None or policy.get("project_id") in (None, project_id)
        ):
            row = _ensure(conn, tenant, policy, at)
            event(conn, row)
    return True


def record_call(conn, identity, call):
    tenant = identity["tenant_id"]
    current = conn.execute(
        "SELECT snapshot FROM runtime_budget_tenants WHERE tenant_id=%s", (tenant,)
    ).fetchone()
    if current:
        for policy in current["snapshot"]["policies"]:
            if not policy.get("deleted_at") and policy.get("project_id") in (
                None,
                identity["project_id"],
            ):
                _ensure(conn, tenant, policy, utc(call["started_at"]))
    rows = conn.execute(
        "SELECT * FROM runtime_budget_windows WHERE tenant_id=%s "
        "AND window_start <= %s AND window_end > %s "
        "AND (valid_until IS NULL OR valid_until > %s) "
        "AND (policy->>'project_id' IS NULL OR policy->>'project_id'=%s)",
        (
            tenant,
            call["started_at"],
            call["started_at"],
            call["started_at"],
            identity["project_id"],
        ),
    ).fetchall()
    for row in rows:
        if row["policy"].get("project_id") not in (None, identity["project_id"]):
            continue
        ident = (
            *key(row),
            identity["project_id"],
            identity["run_id"],
            call["model_call_id"],
        )
        old = conn.execute(
            "SELECT amount FROM runtime_budget_contributions WHERE "
            "(tenant_id,policy_id,definition_version,window_start,project_id,run_id,model_call_id)"
            "=(%s,%s,%s,%s,%s,%s,%s)",
            ident,
        ).fetchone()
        amount = call["estimated_cost_usd"]
        conn.execute(
            "INSERT INTO runtime_budget_contributions "
            "(tenant_id,policy_id,definition_version,window_start,project_id,run_id,model_call_id,amount,pending)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT"
            "(tenant_id,policy_id,definition_version,window_start,project_id,run_id,model_call_id) "
            "DO UPDATE SET amount=EXCLUDED.amount,pending=EXCLUDED.pending",
            (*ident, amount, call["outcome"] == "started"),
        )
        delta = Decimal(str(amount or 0)) - (
            old["amount"] or Decimal(0) if old else Decimal(0)
        )
        updated = conn.execute(
            "UPDATE runtime_budget_windows SET known_spend=known_spend+%s WHERE "
            "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s) RETURNING *",
            (delta, *key(row)),
        ).fetchone()
        event(conn, updated)


def status(conn, row, at):
    facts = conn.execute(
        "SELECT count(*) FILTER (WHERE c.amount IS NULL AND "
        "(NOT c.pending OR l.expires_at IS NULL OR l.expires_at < %s)) AS n, "
        "COALESCE(sum(c.amount),0) AS recorded FROM runtime_budget_contributions c "
        "LEFT JOIN runtime_budget_call_leases l USING(tenant_id,project_id,run_id,model_call_id) WHERE "
        "(c.tenant_id,c.policy_id,c.definition_version,c.window_start)=(%s,%s,%s,%s)",
        (at, *key(row)),
    ).fetchone()
    if facts["recorded"] != row["known_spend"]:
        rebuild(conn, key(row))
        repaired = conn.execute(
            "SELECT * FROM runtime_budget_windows WHERE "
            "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s)",
            key(row),
        ).fetchone()
        return status(conn, repaired, at)
    degraded = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM runtime_usage_runs WHERE tenant_id=%s AND degraded "
        "AND collection_started_at < %s AND COALESCE(collection_ended_at,%s) >= %s "
        "AND (%s::text IS NULL OR project_id=%s)) AS bad",
        (
            row["tenant_id"],
            row["window_end"],
            at,
            row["window_start"],
            row["policy"].get("project_id"),
            row["policy"].get("project_id"),
        ),
    ).fetchone()["bad"]
    exceeded = row["known_spend"] >= Decimal(row["policy"]["budget_amount"])
    complete = not facts["n"] and not degraded
    return {
        "policy_id": str(row["policy_id"]),
        "definition_version": row["definition_version"],
        "window_start": row["window_start"].isoformat(),
        "window_end": row["window_end"].isoformat(),
        "accounting_status": "complete" if complete else "unverifiable",
        "known_spend": format(row["known_spend"], ".12f"),
        "current_spend": format(row["known_spend"], ".12f") if complete else None,
        "is_exceeded": True if exceeded else False if complete else None,
        "as_of": at.isoformat(),
    }


def synchronize(snapshot, *, at=None, project_id=None, nonce=None):
    at = at or datetime.now(UTC)
    with _connection(budget=True) as conn:
        # Control-plane backfill has a larger bound than hot-path usage writes.
        conn.execute("SET LOCAL statement_timeout='4s'")
        conn.execute("SET LOCAL lock_timeout='1s'")
        from runtime_service.gateway_budget.worker_guard import activate

        activate(conn)
        locked(conn, snapshot["tenant_id"])
        if nonce:
            conn.execute(
                "INSERT INTO runtime_budget_nonces(nonce) VALUES(%s)", (nonce,)
            )
        if not apply_snapshot(conn, snapshot, at, project_id):
            raise ValueError("budget_stale_revision")
        return [
            status(conn, _ensure(conn, snapshot["tenant_id"], p, at), at)
            for p in snapshot["policies"]
            if not p.get("deleted_at")
            and (project_id is None or p.get("project_id") in (None, project_id))
        ]


def admit(identity, call, snapshot):
    from runtime_service.db.repositories import usage
    from runtime_service.observability.usage import safe_pricing

    at = utc(call["started_at"])
    price = safe_pricing(call["pricing_snapshot"])
    decision = None
    with _connection(budget=True) as conn:
        locked(conn, identity["tenant_id"])
        if not apply_snapshot(conn, snapshot, at, identity["project_id"]):
            raise ValueError("budget_stale_revision")
        usage._begin(conn, identity)
        existing = conn.execute(
            "SELECT 1 FROM runtime_usage_calls WHERE tenant_id=%s AND project_id=%s AND run_id=%s AND model_call_id=%s",
            (
                identity["tenant_id"],
                identity["project_id"],
                identity["run_id"],
                call["model_call_id"],
            ),
        ).fetchone()
        if existing:
            return {"code": "runtime.gateway_budget.unverifiable"}
        for policy in snapshot["policies"]:
            if policy.get("deleted_at") or policy.get("project_id") not in (
                None,
                identity["project_id"],
            ):
                continue
            state = status(conn, _ensure(conn, identity["tenant_id"], policy, at), at)
            if policy["action"] != "REJECT":
                continue
            if state["is_exceeded"]:
                decision = {
                    "code": "runtime.gateway_budget.exhausted",
                    "resets_at": state["window_end"],
                }
                break
            if (
                state["accounting_status"] != "complete"
                or price is None
                or price["input"] is None
                or price["output"] is None
            ):
                decision = {"code": "runtime.gateway_budget.unverifiable"}
        if decision:
            conn.execute(
                "UPDATE runtime_usage_runs SET gateway_budget_stop_code=%s WHERE "
                "tenant_id=%s AND project_id=%s AND run_id=%s",
                (
                    decision["code"],
                    identity["tenant_id"],
                    identity["project_id"],
                    identity["run_id"],
                ),
            )
        else:
            usage._upsert_call(conn, identity, call)
            conn.execute(
                "INSERT INTO runtime_budget_call_leases "
                "(tenant_id,project_id,run_id,model_call_id,expires_at) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(tenant_id,project_id,run_id,model_call_id) DO UPDATE SET expires_at=EXCLUDED.expires_at",
                (
                    identity["tenant_id"],
                    identity["project_id"],
                    identity["run_id"],
                    call["model_call_id"],
                    at + timedelta(seconds=30),
                ),
            )
    return decision


def renew(identity, call_id):
    with _connection() as conn:
        conn.execute(
            "UPDATE runtime_budget_call_leases SET expires_at=now()+interval '30 seconds' WHERE "
            "tenant_id=%s AND project_id=%s AND run_id=%s AND model_call_id=%s",
            (
                identity["tenant_id"],
                identity["project_id"],
                identity["run_id"],
                str(call_id),
            ),
        )
