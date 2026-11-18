"""Persistent budget projections, contribution identities, liveness and outbox."""

from alembic import op

revision = "0012_gateway_budget"
down_revision = "0011_evaluation_execution"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE runtime_budget_tenants (
        tenant_id text PRIMARY KEY, revision bigint NOT NULL, snapshot jsonb NOT NULL
    );
    CREATE TABLE runtime_budget_windows (
        tenant_id text NOT NULL, policy_id uuid NOT NULL, definition_version bigint NOT NULL,
        window_start timestamptz NOT NULL, window_end timestamptz NOT NULL,
        valid_until timestamptz, policy jsonb NOT NULL,
        known_spend numeric(28,12) NOT NULL DEFAULT 0 CHECK(known_spend >= 0),
        PRIMARY KEY(tenant_id,policy_id,definition_version,window_start)
    );
    CREATE TABLE runtime_budget_contributions (
        tenant_id text NOT NULL, policy_id uuid NOT NULL, definition_version bigint NOT NULL,
        window_start timestamptz NOT NULL, project_id text NOT NULL, run_id uuid NOT NULL,
        model_call_id uuid NOT NULL, amount numeric(28,12), pending boolean NOT NULL,
        PRIMARY KEY(tenant_id,policy_id,definition_version,window_start,project_id,run_id,model_call_id)
    );
    CREATE TABLE runtime_budget_outbox (
        event_id uuid PRIMARY KEY, tenant_id text NOT NULL, policy_id uuid NOT NULL,
        definition_version bigint NOT NULL, window_start timestamptz NOT NULL,
        payload jsonb NOT NULL, attempts integer NOT NULL DEFAULT 0,
        next_attempt_at timestamptz NOT NULL DEFAULT now(), delivered_at timestamptz,
        last_error text,
        UNIQUE(tenant_id,policy_id,definition_version,window_start)
    );
    CREATE INDEX ix_budget_outbox_pending ON runtime_budget_outbox(next_attempt_at)
        WHERE delivered_at IS NULL;
    CREATE TABLE runtime_budget_call_leases (
        tenant_id text NOT NULL, project_id text NOT NULL, run_id uuid NOT NULL,
        model_call_id uuid NOT NULL, expires_at timestamptz NOT NULL,
        PRIMARY KEY(tenant_id,project_id,run_id,model_call_id)
    );
    CREATE TABLE runtime_budget_nonces (
        nonce uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now()
    );
    ALTER TABLE runtime_usage_runs ADD COLUMN gateway_budget_stop_code text;
    """)


def downgrade():
    raise RuntimeError("Budget and usage history must be retained")
