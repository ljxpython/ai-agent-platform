/**
 * 定时 Agent 任务前端类型定义
 */

export type ScheduleType = "cron" | "once";
export type ThreadMode = "fresh" | "reuse";
export type ScheduleStatus = "active" | "paused" | "exhausted";

export interface ScheduledTask {
  id: string;
  title: string;
  prompt: string;
  agent_key: string;
  schedule_type: ScheduleType;
  cron?: string | null;
  run_at?: string | null;
  timezone: string;
  end_time?: string | null;
  thread_mode: ThreadMode;
  thread_id?: string | null;
  context: Record<string, any>;
  enabled: boolean;
  schedule_status: ScheduleStatus;
  next_run_at: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskRun {
  cron_id: string;
  run_id: string;
  thread_id: string;
  status:
    | "pending"
    | "running"
    | "success"
    | "error"
    | "timeout"
    | "interrupted";
  trigger: "scheduled" | "manual";
  created_at: string;
  updated_at: string;
  error_code: string | null;
}

export interface TaskCreatePayload {
  title: string;
  prompt: string;
  agent_key: string;
  schedule_type: ScheduleType;
  cron?: string | null;
  run_at?: string | null;
  timezone: string;
  end_time?: string | null;
  thread_mode: ThreadMode;
  thread_id?: string | null;
  context?: Record<string, any>;
  enabled?: boolean;
}

export interface TaskUpdatePayload {
  title?: string;
  prompt?: string;
  cron?: string;
  run_at?: string;
  timezone?: string;
  end_time?: string | null;
  context?: Record<string, any>;
}

export interface SchedulePreviewPayload {
  schedule_type: ScheduleType;
  cron?: string | null;
  run_at?: string | null;
  timezone: string;
  end_time?: string | null;
}

export interface SchedulePreviewResult {
  times: string[];
  timezone: string;
}

export interface TriggerTaskResult {
  run_id: string;
  thread_id: string;
  status: string;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
