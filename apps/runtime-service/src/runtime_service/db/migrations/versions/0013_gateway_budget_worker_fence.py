"""Sticky execution fence: a rollback must pause, never bypass a saved budget."""

from alembic import op

revision = "0013_budget_worker_fence"
down_revision = "0012_gateway_budget"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE runtime_budget_worker_fence (
        id integer PRIMARY KEY CHECK(id=1), active boolean NOT NULL DEFAULT false
    );
    INSERT INTO runtime_budget_worker_fence(id) VALUES(1);
    CREATE FUNCTION runtime_budget_worker_fence() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.status='running' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM 'running') THEN
            PERFORM pg_advisory_xact_lock_shared(81019, 1);
            IF (SELECT active FROM runtime_budget_worker_fence WHERE id=1)
                AND current_setting('runtime.gateway_budget_guard',true) IS DISTINCT FROM 'v1' THEN
                RAISE EXCEPTION 'gateway budget worker capability required' USING ERRCODE='55000';
            END IF;
        END IF;
        RETURN NEW;
    END $$;
    DO $$ BEGIN
        IF to_regclass('runs') IS NOT NULL THEN
            CREATE TRIGGER runtime_budget_worker_fence BEFORE INSERT OR UPDATE OF status ON runs
                FOR EACH ROW EXECUTE FUNCTION runtime_budget_worker_fence();
        END IF;
    END $$;
    """)


def downgrade():
    raise RuntimeError(
        "Keep the worker fence active; rollback requires pausing execution"
    )
