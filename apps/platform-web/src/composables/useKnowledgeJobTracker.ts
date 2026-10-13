import { shallowRef } from "vue";
import {
  getKnowledgeJob,
  isValidJobId,
  type KnowledgeJob,
  type KnowledgeStatus,
} from "@/services/knowledge/knowledge.service";

const NON_TERMINAL_STATUSES: Set<KnowledgeStatus> = new Set([
  "queued",
  "parsing",
  "indexing",
  "publishing",
]);

// 单例状态
const jobsState = shallowRef<Map<string, KnowledgeJob>>(new Map());
const jobProjects = new Map<string, string>();
const subscribers = new Map<string, Set<(job: KnowledgeJob) => void>>();

let timer: number | null = null;
let currentBackoffMs = 3500;
const BASE_POLL_INTERVAL_MS = 3500;
const MAX_BACKOFF_MS = 30000;

let isListeningVisibility = false;
let isPageVisible = typeof document !== "undefined" ? !document.hidden : true;

function notifySubscribers(job: KnowledgeJob) {
  const set = subscribers.get(job.job_id);
  if (set) {
    set.forEach((cb) => {
      try {
        cb(job);
      } catch (err) {
        console.error("[useKnowledgeJobTracker] 订阅回调异常:", err);
      }
    });
  }
}

function updateJobInState(job: KnowledgeJob) {
  const existing = jobsState.value.get(job.job_id);
  // 状态防倒退：若本地已有终态（ready/failed），禁止被后到的中间态覆盖
  if (
    existing &&
    (existing.status === "ready" || existing.status === "failed") &&
    NON_TERMINAL_STATUSES.has(job.status)
  ) {
    return;
  }
  const next = new Map(jobsState.value);
  next.set(job.job_id, job);
  jobsState.value = next;
  notifySubscribers(job);
}

function getActiveJobIds(): string[] {
  const active: string[] = [];
  for (const [jobId, job] of jobsState.value.entries()) {
    if (NON_TERMINAL_STATUSES.has(job.status)) {
      active.push(jobId);
    }
  }
  return active;
}

async function pollOnce() {
  if (!isPageVisible) return;

  const activeJobIds = getActiveJobIds();
  if (activeJobIds.length === 0) {
    stopPolling();
    return;
  }

  let hasError = false;

  for (const jobId of activeJobIds) {
    const projectId = jobProjects.get(jobId);
    if (!projectId) continue;

    try {
      const updatedJob = await getKnowledgeJob(projectId, jobId);
      updateJobInState(updatedJob);
      currentBackoffMs = BASE_POLL_INTERVAL_MS;
    } catch (err: unknown) {
      hasError = true;
      const status = (err as { response?: { status?: number } })?.response
        ?.status;
      if (status === 401 || status === 403 || status === 404) {
        // 权限失效或任务不可见，停轮询，标明为鉴权失效/未找到，不误导为解析崩溃
        const current = jobsState.value.get(jobId);
        if (current) {
          updateJobInState({
            ...current,
            status: "failed",
            error_code:
              status === 404
                ? "knowledge_not_found"
                : "knowledge_authorization_denied",
            updated_at: new Date().toISOString(),
          });
        }
      }
    }
  }

  if (hasError) {
    currentBackoffMs = Math.min(currentBackoffMs * 1.5, MAX_BACKOFF_MS);
  }
}

function scheduleNext() {
  if (timer !== null) {
    window.clearTimeout(timer);
    timer = null;
  }

  if (!isPageVisible) return;
  if (getActiveJobIds().length === 0) return;

  timer = window.setTimeout(async () => {
    await pollOnce();
    scheduleNext();
  }, currentBackoffMs);
}

function startPolling() {
  if (timer !== null) return;
  scheduleNext();
}

function stopPolling() {
  if (timer !== null) {
    window.clearTimeout(timer);
    timer = null;
  }
}

function setupVisibilityListener() {
  if (isListeningVisibility || typeof document === "undefined") return;
  isListeningVisibility = true;

  document.addEventListener("visibilitychange", () => {
    isPageVisible = !document.hidden;
    if (isPageVisible) {
      currentBackoffMs = BASE_POLL_INTERVAL_MS;
      void pollOnce().then(() => scheduleNext());
    } else {
      stopPolling();
    }
  });
}

export function useKnowledgeJobTracker() {
  setupVisibilityListener();

  /**
   * 注册并追踪一个任务
   */
  function trackJob(
    projectId: string,
    jobId: string,
    initial?: Partial<KnowledgeJob>,
    callback?: (job: KnowledgeJob) => void,
  ) {
    if (!jobId || !isValidJobId(jobId)) return () => {};

    let unsubscribe = () => {};
    if (callback) {
      unsubscribe = subscribeJob(jobId, callback);
    }

    jobProjects.set(jobId, projectId);

    const existing = jobsState.value.get(jobId);
    if (initial) {
      let statusToUse = initial.status || existing?.status || "queued";
      if (
        existing &&
        (existing.status === "ready" || existing.status === "failed")
      ) {
        statusToUse = existing.status;
      }
      const jobData: KnowledgeJob = {
        version: 1,
        job_id: jobId,
        document_id: initial.document_id || existing?.document_id || "",
        file_name: initial.file_name || existing?.file_name || "document",
        status: statusToUse,
        searchable:
          existing && existing.status === "ready"
            ? existing.searchable
            : Boolean(initial.searchable ?? existing?.searchable),
        error_code: initial.error_code ?? existing?.error_code ?? null,
        created_at:
          initial.created_at ||
          existing?.created_at ||
          new Date().toISOString(),
        updated_at:
          initial.updated_at ||
          existing?.updated_at ||
          new Date().toISOString(),
      };
      updateJobInState(jobData);
    }

    const current = jobsState.value.get(jobId);
    if (current && NON_TERMINAL_STATUSES.has(current.status)) {
      startPolling();
    }

    return unsubscribe;
  }

  /**
   * 订阅指定任务的状态变更
   */
  function subscribeJob(jobId: string, callback: (job: KnowledgeJob) => void) {
    if (!subscribers.has(jobId)) {
      subscribers.set(jobId, new Set());
    }
    subscribers.get(jobId)!.add(callback);

    // 初始如果已有状态，立即回调一次
    const current = jobsState.value.get(jobId);
    if (current) {
      callback(current);
    }

    return () => {
      const set = subscribers.get(jobId);
      if (set) {
        set.delete(callback);
        if (set.size === 0) {
          subscribers.delete(jobId);
        }
      }
    };
  }

  /**
   * 获取指定任务的当前状态
   */
  function getJob(jobId: string): KnowledgeJob | undefined {
    return jobsState.value.get(jobId);
  }

  /**
   * 切项目或注销时重置所有任务
   */
  function resetAll() {
    stopPolling();
    jobsState.value = new Map();
    jobProjects.clear();
    subscribers.clear();
  }

  return {
    jobsState,
    activeJobs: jobsState,
    trackJob,
    subscribeJob,
    getJob,
    resetAll,
    reset: resetAll,
    pollNow: pollOnce,
  };
}
