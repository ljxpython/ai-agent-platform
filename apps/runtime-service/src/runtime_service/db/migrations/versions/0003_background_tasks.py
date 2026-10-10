"""Owned background resources and one completion intent per task."""

from alembic import op

revision = "0003_background_tasks"
down_revision = "0002_run_control"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE IF NOT EXISTS runtime_background_tasks (
 task_id uuid PRIMARY KEY, tenant_id text NOT NULL, project_id text NOT NULL,
 owner_id text NOT NULL, credential_id text, graph_id text NOT NULL, thread_id text NOT NULL,
 origin_run_id text NOT NULL, checkpoint_ns text NOT NULL, tool_call_id text NOT NULL,
 submission_key text NOT NULL UNIQUE, request_digest text NOT NULL,
 execution_host_id text NOT NULL, container_name text NOT NULL UNIQUE, container_id text,
 binding_digest text NOT NULL, runner_secret text NOT NULL, resource_id uuid NOT NULL UNIQUE,
 status text NOT NULL DEFAULT 'starting', exit_code integer, reason_code text,
 started_at timestamptz, finished_at timestamptz, deadline_at timestamptz NOT NULL,
 cleanup_state text NOT NULL DEFAULT 'pending',
 log_reserved boolean NOT NULL DEFAULT true, log_bytes integer NOT NULL DEFAULT 0,
 omitted_bytes bigint NOT NULL DEFAULT 0, output_available boolean NOT NULL DEFAULT false,
 output_truncated boolean NOT NULL DEFAULT false, log_updated_at timestamptz, log_fence bigint,
 next_check_at timestamptz NOT NULL DEFAULT now(), lease_token uuid, lease_until timestamptz,
 fence bigint NOT NULL DEFAULT 0, attempts integer NOT NULL DEFAULT 0,
 cancel_requested_at timestamptz,
 event_id uuid NOT NULL UNIQUE, delivery_state text NOT NULL DEFAULT 'not_ready',
 notification_deadline_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
 delivery_run_id text, delivery_accepted_at timestamptz, delivery_inflight boolean NOT NULL DEFAULT false,
 delivery_cancel_confirmed boolean NOT NULL DEFAULT false, delivery_attempts integer NOT NULL DEFAULT 0,
 delivery_reason text, stop_id uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT now(),
 request_id text, platform_trace_id text,
 UNIQUE(tenant_id,project_id,graph_id,thread_id,origin_run_id,checkpoint_ns,tool_call_id),
 CHECK(status IN ('starting','running','succeeded','failed','timed_out','cancel_requested','cancelled','unknown')),
 CHECK(cleanup_state IN ('not_required','pending','confirmed','unconfirmed')),
 CHECK(delivery_state IN ('not_ready','pending','dispatching','accepted','blocked','suppressed','expired','unknown')),
 CHECK(log_bytes BETWEEN 0 AND 1048576 AND omitted_bytes >= 0)
);
CREATE INDEX IF NOT EXISTS runtime_background_due ON runtime_background_tasks(execution_host_id,next_check_at)
 WHERE cleanup_state IN ('pending','unconfirmed') OR delivery_state IN ('pending','dispatching','blocked','unknown')
 OR (stop_id IS NOT NULL AND (delivery_inflight OR (delivery_run_id IS NOT NULL AND NOT delivery_cancel_confirmed)));
CREATE INDEX IF NOT EXISTS runtime_background_logs ON runtime_background_tasks(execution_host_id,created_at)
 WHERE log_reserved AND cleanup_state IN ('confirmed','not_required');
CREATE INDEX IF NOT EXISTS runtime_background_scope ON runtime_background_tasks(tenant_id,project_id,graph_id,thread_id,created_at DESC,task_id DESC);
CREATE INDEX IF NOT EXISTS runtime_background_origin ON runtime_background_tasks(thread_id,origin_run_id);
CREATE INDEX IF NOT EXISTS runtime_background_active ON runtime_background_tasks(execution_host_id,tenant_id,project_id,thread_id)
 WHERE cleanup_state IN ('pending','unconfirmed');
CREATE INDEX IF NOT EXISTS runtime_background_reserved ON runtime_background_tasks(execution_host_id) WHERE log_reserved;
CREATE INDEX IF NOT EXISTS runtime_background_latest_delivery ON runtime_background_tasks(tenant_id,project_id,graph_id,thread_id,delivery_accepted_at DESC,task_id DESC)
 WHERE delivery_run_id IS NOT NULL;
ALTER TABLE runtime_stop_requests ADD COLUMN IF NOT EXISTS background_task_ids jsonb NOT NULL DEFAULT '[]';
ALTER TABLE runtime_stop_requests ADD COLUMN IF NOT EXISTS background_event_ids jsonb NOT NULL DEFAULT '[]';
""")


def downgrade():
    # Old Runtime ignores additive receipts; replay protection survives rollback.
    pass
