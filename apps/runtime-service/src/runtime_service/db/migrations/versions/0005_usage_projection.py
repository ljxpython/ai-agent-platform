"""Rebuildable usage buckets; retain every call and the application migration chain."""

from alembic import op

revision = "0005_usage_projection"
down_revision = "0004_usage_analytics"
branch_labels = None
depends_on = None


def upgrade():
    tokens = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
        "cache_creation_5m_tokens",
        "cache_creation_1h_tokens",
        "reasoning_tokens",
    )
    columns = ",".join(
        f"{name} numeric, {name}_count bigint NOT NULL" for name in tokens
    )
    op.execute(f"""
ALTER TABLE runtime_usage_runs ADD COLUMN usage_slot integer;
WITH slots AS (SELECT tenant_id,project_id,run_id,
    row_number() OVER (PARTITION BY tenant_id,project_id ORDER BY run_id)-1 AS slot FROM runtime_usage_runs)
UPDATE runtime_usage_runs r SET usage_slot=s.slot FROM slots s
WHERE r.tenant_id=s.tenant_id AND r.project_id=s.project_id AND r.run_id=s.run_id;
ALTER TABLE runtime_usage_runs ALTER COLUMN usage_slot SET NOT NULL;
ALTER TABLE runtime_usage_runs ADD CONSTRAINT runtime_usage_runs_slot_key UNIQUE (tenant_id,project_id,usage_slot);
CREATE TABLE runtime_usage_run_slots (
    tenant_id text NOT NULL,project_id text NOT NULL,last_slot integer NOT NULL,
    PRIMARY KEY (tenant_id,project_id)
);
INSERT INTO runtime_usage_run_slots SELECT tenant_id,project_id,max(usage_slot) FROM runtime_usage_runs GROUP BY 1,2;
CREATE FUNCTION runtime_usage_assign_slot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    SELECT usage_slot INTO NEW.usage_slot FROM runtime_usage_runs
    WHERE tenant_id=NEW.tenant_id AND project_id=NEW.project_id AND run_id=NEW.run_id;
    IF FOUND THEN RETURN NEW; END IF;
    INSERT INTO runtime_usage_run_slots VALUES (NEW.tenant_id,NEW.project_id,0)
    ON CONFLICT (tenant_id,project_id) DO UPDATE SET last_slot=runtime_usage_run_slots.last_slot+1
    RETURNING last_slot INTO NEW.usage_slot;
    RETURN NEW;
END;
$$;
CREATE TRIGGER runtime_usage_run_slot BEFORE INSERT ON runtime_usage_runs
FOR EACH ROW EXECUTE FUNCTION runtime_usage_assign_slot();
ALTER TABLE runtime_usage_runs ADD COLUMN has_calls boolean NOT NULL DEFAULT false;
UPDATE runtime_usage_runs r SET has_calls=true
WHERE EXISTS (SELECT 1 FROM runtime_usage_calls c
    WHERE c.tenant_id=r.tenant_id AND c.project_id=r.project_id AND c.run_id=r.run_id);
CREATE SEQUENCE runtime_usage_projection_generation START 2;
CREATE TABLE runtime_usage_projection_state (
    id integer PRIMARY KEY CHECK (id=1),
    active_generation bigint NOT NULL,
    building_generation bigint,
    seed_complete boolean NOT NULL DEFAULT true,
    seed_tenant text,
    seed_project text,
    switched_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO runtime_usage_projection_state (id,active_generation) VALUES (1,1);
CREATE TABLE runtime_usage_projection_dirty (
    generation bigint NOT NULL, tenant_id text NOT NULL, project_id text NOT NULL,
    utc_day timestamptz NOT NULL, version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    retry_at timestamptz NOT NULL DEFAULT now()+interval '1 second',
    CHECK (generation>0)
);
CREATE INDEX ix_runtime_usage_dirty_scope ON runtime_usage_projection_dirty (generation,tenant_id,project_id,utc_day,version);
CREATE FUNCTION runtime_usage_merge_versions(a text[],b text[]) RETURNS text[]
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    IF a=b OR cardinality(b)=0 THEN RETURN a; END IF;
    RETURN ARRAY(SELECT DISTINCT v FROM unnest(a || b) v ORDER BY v LIMIT 51);
END;
$$;
CREATE AGGREGATE runtime_usage_versions(text[]) (
    SFUNC=runtime_usage_merge_versions, STYPE=text[], INITCOND='{{}}',
    COMBINEFUNC=runtime_usage_merge_versions, PARALLEL=SAFE
);
CREATE TABLE runtime_usage_buckets (
    generation bigint NOT NULL, tenant_id text NOT NULL, project_id text NOT NULL,
    grain smallint NOT NULL CHECK (grain IN (0,1,2,3)), bucket timestamptz NOT NULL,
    graph_id text NOT NULL, model_key text NOT NULL, purpose text NOT NULL, scope text NOT NULL,
    observed_call_count bigint NOT NULL, reported_call_count bigint NOT NULL,
    missing_usage_call_count bigint NOT NULL, incomplete_call_count bigint NOT NULL,
    priced_call_count bigint NOT NULL, known_cost_usd numeric,
    ratio_sample_call_count bigint NOT NULL, ratio_input_tokens numeric, ratio_cache_tokens numeric,
    {columns}, run_ids bit varying NOT NULL, pricing_versions text[] NOT NULL,
    PRIMARY KEY (generation,tenant_id,project_id,grain,bucket,graph_id,model_key,purpose,scope)
);
INSERT INTO runtime_usage_projection_dirty (generation,tenant_id,project_id,utc_day)
SELECT DISTINCT 1,tenant_id,project_id,date_trunc('day',started_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
FROM runtime_usage_calls;

CREATE FUNCTION runtime_usage_mark_dirty() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE active bigint; building bigint;
BEGIN
    IF TG_OP='INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM new_calls) THEN RETURN NULL; END IF;
    ELSIF TG_OP='UPDATE' THEN
        IF NOT EXISTS (SELECT 1 FROM new_calls) THEN RETURN NULL; END IF;
    ELSE
        IF NOT EXISTS (SELECT 1 FROM old_calls) THEN RETURN NULL; END IF;
    END IF;
    -- Share locks make generation creation/switching wait for in-flight fact writes.
    SELECT active_generation,building_generation INTO active,building
    FROM runtime_usage_projection_state WHERE id=1 FOR SHARE;
    IF TG_OP <> 'DELETE' THEN
        INSERT INTO runtime_usage_projection_dirty (generation,tenant_id,project_id,utc_day)
        SELECT g,tenant_id,project_id,date_trunc('day',started_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        FROM new_calls CROSS JOIN unnest(ARRAY[active,building]) g WHERE g IS NOT NULL
        GROUP BY 1,2,3,4;
    END IF;
    IF TG_OP <> 'INSERT' THEN
        INSERT INTO runtime_usage_projection_dirty (generation,tenant_id,project_id,utc_day)
        SELECT g,tenant_id,project_id,date_trunc('day',started_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        FROM old_calls CROSS JOIN unnest(ARRAY[active,building]) g WHERE g IS NOT NULL
        GROUP BY 1,2,3,4;
    END IF;
    IF TG_OP='INSERT' THEN
        UPDATE runtime_usage_runs r SET has_calls=true
        FROM (SELECT DISTINCT tenant_id,project_id,run_id FROM new_calls) c
        WHERE NOT r.has_calls AND r.tenant_id=c.tenant_id AND r.project_id=c.project_id AND r.run_id=c.run_id;
    ELSIF TG_OP='DELETE' THEN
        UPDATE runtime_usage_runs r SET has_calls=EXISTS (
            SELECT 1 FROM runtime_usage_calls c WHERE c.tenant_id=r.tenant_id AND c.project_id=r.project_id AND c.run_id=r.run_id)
        FROM (SELECT DISTINCT tenant_id,project_id,run_id FROM old_calls) c
        WHERE r.tenant_id=c.tenant_id AND r.project_id=c.project_id AND r.run_id=c.run_id;
    ELSIF TG_OP='UPDATE' THEN
        UPDATE runtime_usage_runs r SET has_calls=EXISTS (
            SELECT 1 FROM runtime_usage_calls c WHERE c.tenant_id=r.tenant_id AND c.project_id=r.project_id AND c.run_id=r.run_id)
        FROM (SELECT tenant_id,project_id,run_id FROM old_calls
              EXCEPT SELECT tenant_id,project_id,run_id FROM new_calls) c
        WHERE r.tenant_id=c.tenant_id AND r.project_id=c.project_id AND r.run_id=c.run_id;
            UPDATE runtime_usage_runs r SET has_calls=true
            FROM (SELECT DISTINCT tenant_id,project_id,run_id FROM new_calls) c
            WHERE NOT r.has_calls AND r.tenant_id=c.tenant_id AND r.project_id=c.project_id AND r.run_id=c.run_id;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER runtime_usage_insert_dirty AFTER INSERT ON runtime_usage_calls
REFERENCING NEW TABLE AS new_calls FOR EACH STATEMENT EXECUTE FUNCTION runtime_usage_mark_dirty();
CREATE TRIGGER runtime_usage_update_dirty AFTER UPDATE ON runtime_usage_calls
REFERENCING OLD TABLE AS old_calls NEW TABLE AS new_calls FOR EACH STATEMENT EXECUTE FUNCTION runtime_usage_mark_dirty();
CREATE TRIGGER runtime_usage_delete_dirty AFTER DELETE ON runtime_usage_calls
REFERENCING OLD TABLE AS old_calls FOR EACH STATEMENT EXECUTE FUNCTION runtime_usage_mark_dirty();
""")


def downgrade():
    raise RuntimeError(
        "Retain usage facts, buckets and migration chain; roll back application readers"
    )
