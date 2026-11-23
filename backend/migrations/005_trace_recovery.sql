-- 追因任务快照与恢复：提交时定格受理票据，运行状态支持认领与超时回收。
ALTER TABLE trace_run DROP CONSTRAINT IF EXISTS trace_run_status_check;
ALTER TABLE trace_run
    ADD CONSTRAINT trace_run_status_check
    CHECK (status IN ('queued', 'running', 'ready', 'blocked', 'failed'));
ALTER TABLE trace_run ADD COLUMN IF NOT EXISTS attempt integer NOT NULL DEFAULT 0;
ALTER TABLE trace_run ADD COLUMN IF NOT EXISTS claimed_at timestamptz;
ALTER TABLE trace_run ADD COLUMN IF NOT EXISTS snapshot jsonb;
CREATE INDEX IF NOT EXISTS trace_run_recovery ON trace_run(claimed_at) WHERE status = 'running';
