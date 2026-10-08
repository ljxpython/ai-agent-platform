"""Runtime-owned model-call facts; engine lifecycle remains in GraphHarbor."""

from alembic import op

revision = "0002_usage"
down_revision = "0001_application"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE runtime_usage_runs (
    tenant_id text NOT NULL, project_id text NOT NULL,
    run_id uuid NOT NULL, thread_id uuid NOT NULL, graph_id text NOT NULL,
    schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version = 1),
    collection_started_at timestamptz NOT NULL DEFAULT now(),
    collection_ended_at timestamptz,
    degraded boolean NOT NULL DEFAULT false,
    PRIMARY KEY (tenant_id, project_id, run_id),
    UNIQUE (tenant_id, project_id, run_id, thread_id, graph_id)
);
CREATE INDEX ix_runtime_usage_runs_thread ON runtime_usage_runs
    (tenant_id, project_id, thread_id, graph_id, collection_started_at);
CREATE TABLE runtime_usage_calls (
    tenant_id text NOT NULL, project_id text NOT NULL, run_id uuid NOT NULL,
    thread_id uuid NOT NULL, graph_id text NOT NULL,
    model_call_id uuid NOT NULL, parent_call_id uuid,
    model_id uuid, provider text, model_name text,
    scope text NOT NULL CHECK (scope IN ('primary', 'subagent', 'auxiliary')),
    purpose text NOT NULL, namespace jsonb NOT NULL DEFAULT '[]',
    outcome text NOT NULL CHECK (outcome IN ('started', 'completed', 'failed', 'cancelled')),
    quality text NOT NULL CHECK (quality IN ('reported', 'derived_from_reported', 'partial', 'missing', 'invalid')),
    usage_source text NOT NULL,
    token_details jsonb NOT NULL DEFAULT '{}',
    input_tokens bigint CHECK (input_tokens >= 0),
    output_tokens bigint CHECK (output_tokens >= 0),
    total_tokens bigint CHECK (total_tokens >= 0),
    cache_read_tokens bigint CHECK (cache_read_tokens >= 0),
    cache_creation_tokens bigint CHECK (cache_creation_tokens >= 0),
    cache_creation_5m_tokens bigint CHECK (cache_creation_5m_tokens >= 0),
    cache_creation_1h_tokens bigint CHECK (cache_creation_1h_tokens >= 0),
    reasoning_tokens bigint CHECK (reasoning_tokens >= 0),
    pricing_snapshot jsonb,
    estimated_cost_usd numeric(28,12) CHECK (estimated_cost_usd >= 0),
    cost_reason text,
    started_at timestamptz NOT NULL, ended_at timestamptz,
    PRIMARY KEY (tenant_id, project_id, run_id, model_call_id),
    FOREIGN KEY (tenant_id, project_id, run_id, thread_id, graph_id)
        REFERENCES runtime_usage_runs (tenant_id, project_id, run_id, thread_id, graph_id)
);
CREATE INDEX ix_runtime_usage_calls_page ON runtime_usage_calls
    (tenant_id, project_id, run_id, started_at, model_call_id);
CREATE INDEX ix_runtime_usage_calls_thread ON runtime_usage_calls
    (tenant_id, project_id, thread_id, graph_id, run_id);
""")


def downgrade():
    raise RuntimeError(
        "Usage facts are retained; destructive downgrade is not supported"
    )
