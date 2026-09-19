"""Runtime-owned schema; legacy skill versions are deliberately not imported."""
from alembic import op
from sqlalchemy import inspect

revision = "0001_application"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE IF NOT EXISTS dear_external_tasks (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL, project_id text NOT NULL, user_id text NOT NULL,
    graph_id text NOT NULL DEFAULT 'dearflow_agent' CHECK (graph_id='dearflow_agent'),
    thread_id text NOT NULL, origin_run_id text NOT NULL, approval_ref text NOT NULL,
    idem_key text NOT NULL, operation text NOT NULL, request jsonb NOT NULL,
    digest text NOT NULL, status text NOT NULL DEFAULT 'intent',
    result jsonb NOT NULL DEFAULT '{}', error_code text,
    fence bigint NOT NULL DEFAULT 0, lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    deadline_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,project_id,user_id,thread_id,idem_key),
    CHECK (status IN ('intent','succeeded','unknown'))
);

CREATE TABLE IF NOT EXISTS dear_memory (tenant_id text NOT NULL, project_id text NOT NULL, user_id text NOT NULL, document jsonb NOT NULL, PRIMARY KEY (tenant_id, project_id, user_id));
CREATE TABLE IF NOT EXISTS dear_skills (tenant_id text NOT NULL, project_id text NOT NULL, user_id text NOT NULL, slug text NOT NULL, document jsonb NOT NULL, PRIMARY KEY (tenant_id, project_id, user_id, slug));
CREATE TABLE IF NOT EXISTS runtime_message_inbox (
                message_id uuid PRIMARY KEY, thread_id text NOT NULL,
                target_run_id text NOT NULL, sender_id text NOT NULL,
                authorization_ref text, idem_key text NOT NULL, payload jsonb NOT NULL, digest text NOT NULL,
                sequence bigint NOT NULL, status text NOT NULL DEFAULT 'queued',
                reason text, claim_token uuid, claim_until timestamptz,
                consumed_checkpoint_id text, created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE(thread_id, sender_id, idem_key), UNIQUE(thread_id, sequence));
ALTER TABLE runtime_message_inbox ADD COLUMN IF NOT EXISTS authorization_ref text;
""")
    # Refuse to stamp incompatible existing tables. No destructive repair.
    inspector = inspect(op.get_bind())
    required = {
        "dear_memory": {"tenant_id", "project_id", "user_id", "document"},
        "dear_skills": {"tenant_id", "project_id", "user_id", "slug", "document"},
        "dear_external_tasks": {"graph_id", "id", "tenant_id", "project_id", "user_id", "thread_id", "idem_key", "operation", "request", "digest", "origin_run_id", "approval_ref", "status", "result", "error_code", "fence", "lease_until", "attempts", "deadline_at", "created_at", "updated_at"},
        "runtime_message_inbox": {"message_id", "thread_id", "target_run_id", "sender_id", "authorization_ref", "idem_key", "payload", "digest", "sequence", "status", "reason", "claim_token", "claim_until", "consumed_checkpoint_id", "created_at", "updated_at"},
    }
    primary_keys = {
        "dear_memory": ["tenant_id", "project_id", "user_id"],
        "dear_skills": ["tenant_id", "project_id", "user_id", "slug"],
        "dear_external_tasks": ["id"],
        "runtime_message_inbox": ["message_id"],
    }
    unique_keys = {
        "dear_external_tasks": {("tenant_id", "project_id", "user_id", "thread_id", "idem_key")},
        "runtime_message_inbox": {("thread_id", "sender_id", "idem_key"), ("thread_id", "sequence")},
    }
    for table, columns in required.items():
        actual = {c["name"]: c for c in inspector.get_columns(table)}
        valid = columns <= actual.keys()
        valid &= inspector.get_pk_constraint(table)["constrained_columns"] == primary_keys[table]
        valid &= unique_keys.get(table, set()) <= {tuple(c["column_names"]) for c in inspector.get_unique_constraints(table)}
        for name in columns & actual.keys():
            expected_type = ("JSONB" if name in {"document", "request", "result", "payload"} else
                             "UUID" if name in {"id", "message_id", "claim_token"} else
                             "BIGINT" if name in {"fence", "sequence"} else
                             "INTEGER" if name == "attempts" else
                             "TIMESTAMP" if name.endswith("_at") or name in {"claim_until", "lease_until"} else "TEXT")
            valid &= str(actual[name]["type"]) == expected_type
        if not valid:
            raise RuntimeError(f"incompatible_application_table: {table}")


def downgrade():
    raise RuntimeError("Application data is retained; destructive downgrade is not supported")
