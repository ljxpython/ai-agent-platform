"""Runtime stop actions and resource cleanup evidence, never engine Run state."""

from alembic import op

revision = "0002_run_control"
down_revision = "0002_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE IF NOT EXISTS runtime_stop_requests (
    stop_id uuid PRIMARY KEY, tenant_id text NOT NULL, project_id text NOT NULL,
    thread_id text NOT NULL, actor_scope text NOT NULL, idem_hash text NOT NULL,
    auth_facts jsonb NOT NULL, inbox_run_ids jsonb NOT NULL DEFAULT '[]',
    reconciled_count integer NOT NULL DEFAULT 0,
    audit_pending jsonb NOT NULL DEFAULT '["accepted"]', phase text NOT NULL DEFAULT 'accepted',
    engine_receipt jsonb, report jsonb, reason_code text,
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    accepted_at timestamptz, confirmed_at timestamptz,
    lease_token uuid, lease_until timestamptz, retry_at timestamptz NOT NULL DEFAULT now(),
    attempts integer NOT NULL DEFAULT 0,
    UNIQUE(tenant_id,project_id,thread_id,actor_scope,idem_hash),
    CHECK (phase IN ('accepted','stopping','stopped','no_active_run','confirmation_unavailable','rejected'))
);
ALTER TABLE runtime_stop_requests ADD COLUMN IF NOT EXISTS inbox_run_ids jsonb NOT NULL DEFAULT '[]';
ALTER TABLE runtime_stop_requests ADD COLUMN IF NOT EXISTS reconciled_count integer NOT NULL DEFAULT 0;
ALTER TABLE runtime_stop_requests ADD COLUMN IF NOT EXISTS audit_pending jsonb NOT NULL DEFAULT '["accepted"]';
CREATE INDEX IF NOT EXISTS runtime_stop_pending ON runtime_stop_requests(retry_at);
CREATE INDEX IF NOT EXISTS runtime_stop_thread ON runtime_stop_requests(tenant_id,project_id,thread_id,requested_at,stop_id);
CREATE TABLE IF NOT EXISTS runtime_run_resources (
    resource_id uuid PRIMARY KEY, thread_id text NOT NULL, run_id text NOT NULL,
    kind text NOT NULL, status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status IN ('active','cleanup_confirmed','cleanup_unconfirmed'))
);
CREATE INDEX IF NOT EXISTS runtime_resource_run ON runtime_run_resources(thread_id,run_id);
""")


def downgrade():
    # Keep receipts on rollback; old Runtime ignores these additive tables.
    pass
