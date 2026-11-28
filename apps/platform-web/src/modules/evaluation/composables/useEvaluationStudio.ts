import { computed, ref, type Ref } from "vue";
import {
  archiveSuite,
  checkReadiness,
  compareRuns,
  controlRun,
  createMatrixRuns,
  createPatrol,
  createRun,
  createSuite,
  createSuiteFromSessions,
  deleteCase,
  deletePatrol,
  deleteRun,
  getRunDetail,
  getRunLogs,
  getSuiteDetail,
  importSuiteCases,
  listPatrols,
  listRuns,
  listSuites,
  previewPatrolCron,
  publishSuiteVersion,
  setSandboxFlag,
  submitHumanReview,
  triggerPatrol,
  updatePatrol,
  upsertCase,
  type CaseUpsertPayload,
  type CompareRunsResult,
  type EvalCaseItem,
  type EvalRunCaseItem,
  type EvalRunItem,
  type EvalSuiteItem,
  type EvalSuiteVersionSummary,
  type PatrolCreatePayload,
  type PatrolScheduleItem,
  type PatrolUpdatePayload,
  type ReadinessResult,
} from "@/services/evaluation/studio";
import { resolvePlatformHttpErrorMessage } from "@/utils/http-error";

export function useEvaluationStudio(projectId: Ref<string>) {
  const loading = ref(false);
  const busyAction = ref(false);
  const error = ref("");
  const notice = ref("");
  const suites = ref<EvalSuiteItem[]>([]);
  const activeSuite = ref<EvalSuiteItem | null>(null);
  const suiteCases = ref<EvalCaseItem[]>([]);
  const suiteVersions = ref<EvalSuiteVersionSummary[]>([]);
  const runs = ref<EvalRunItem[]>([]);
  const activeRun = ref<EvalRunItem | null>(null);
  const runCases = ref<EvalRunCaseItem[]>([]);
  const patrols = ref<PatrolScheduleItem[]>([]);
  const readiness = ref<ReadinessResult | null>(null);
  const readinessLoading = ref(false);
  const readinessError = ref("");
  const comparison = ref<CompareRunsResult | null>(null);

  const totalCasesCount = computed(() =>
    suites.value.reduce((acc, s) => acc + (s.case_count ?? 0), 0),
  );
  const publishedSuitesCount = computed(
    () => suites.value.filter((s) => Boolean(s.latest_version)).length,
  );

  async function runSafely<T>(
    label: string,
    fn: () => Promise<T>,
  ): Promise<T | null> {
    error.value = "";
    busyAction.value = true;
    try {
      return await fn();
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        `${label}失败，请稍后重试。`,
        label,
      );
      return null;
    } finally {
      busyAction.value = false;
    }
  }

  async function refreshAll() {
    if (!projectId.value) return;
    loading.value = true;
    error.value = "";
    try {
      const [suiteRows, runRows, patrolRows] = await Promise.all([
        listSuites(projectId.value),
        listRuns(projectId.value),
        listPatrols(projectId.value).catch(() => [] as PatrolScheduleItem[]),
      ]);
      suites.value = suiteRows;
      runs.value = runRows;
      patrols.value = patrolRows;
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        "加载评测数据失败。",
        "评测工坊",
      );
    } finally {
      loading.value = false;
    }
  }

  async function openSuite(suiteId: string) {
    return runSafely("加载题库详情", async () => {
      const detail = await getSuiteDetail(projectId.value, suiteId);
      activeSuite.value = detail.suite;
      suiteCases.value = detail.cases;
      suiteVersions.value = detail.versions;
      return detail;
    });
  }

  async function addSuite(payload: Parameters<typeof createSuite>[1]) {
    return runSafely("创建评测集", async () => {
      const created = await createSuite(projectId.value, payload);
      await refreshAll();
      notice.value = `已创建评测集「${created.name}」。`;
      return created;
    });
  }

  async function removeSuite(suiteId: string) {
    return runSafely("删除评测集", async () => {
      await archiveSuite(projectId.value, suiteId);
      if (activeSuite.value?.id === suiteId) {
        activeSuite.value = null;
        suiteCases.value = [];
        suiteVersions.value = [];
      }
      await refreshAll();
      notice.value = "评测集已归档移除。";
      return true;
    });
  }

  async function convertSessionsToSuite(
    payload: Parameters<typeof createSuiteFromSessions>[1],
  ) {
    return runSafely("从线上会话转化题库", async () => {
      const detail = await createSuiteFromSessions(projectId.value, payload);
      activeSuite.value = detail.suite;
      suiteCases.value = detail.cases;
      suiteVersions.value = detail.versions;
      await refreshAll();
      notice.value = `已从会话沉淀题库「${detail.suite.name}」（共 ${detail.cases.length} 题）。`;
      return detail;
    });
  }

  async function saveCase(suiteId: string, payload: CaseUpsertPayload) {
    return runSafely("保存考题草稿", async () => {
      const saved = await upsertCase(projectId.value, suiteId, payload);
      const idx = suiteCases.value.findIndex(
        (c) => c.case_key === saved.case_key,
      );
      if (idx >= 0) {
        suiteCases.value[idx] = saved;
      } else {
        suiteCases.value = [...suiteCases.value, saved];
      }
      notice.value = `用例「${saved.case_key}」已保存。`;
      return saved;
    });
  }

  async function importCasesBatch(suiteId: string, items: CaseUpsertPayload[]) {
    return runSafely("批量导入考题", async () => {
      const res = await importSuiteCases(projectId.value, suiteId, items);
      await openSuite(suiteId);
      await refreshAll();
      notice.value = `已保存/导入 ${res.imported} 道考题。`;
      return res;
    });
  }

  async function removeCase(suiteId: string, caseKey: string) {
    return runSafely("删除考题", async () => {
      await deleteCase(projectId.value, suiteId, caseKey);
      suiteCases.value = suiteCases.value.filter((c) => c.case_key !== caseKey);
      notice.value = `用例「${caseKey}」已删除。`;
      return true;
    });
  }

  async function publishSuite(suiteId: string) {
    return runSafely("冻结发布版本", async () => {
      const ver = await publishSuiteVersion(projectId.value, suiteId);
      suiteVersions.value = [ver, ...suiteVersions.value];
      await refreshAll();
      notice.value = `已冻结发布新版本 v${ver.version_num} (${ver.content_hash.slice(0, 8)})。`;
      return ver;
    });
  }

  async function runReadiness(payload: Parameters<typeof checkReadiness>[1]) {
    readinessLoading.value = true;
    readinessError.value = "";
    try {
      readiness.value = await checkReadiness(projectId.value, payload);
      return readiness.value;
    } catch (cause) {
      readiness.value = null;
      readinessError.value = resolvePlatformHttpErrorMessage(
        cause,
        "就绪度检查失败，请核对项目权限或模型状态。",
        "就绪度守卫",
      );
      return null;
    } finally {
      readinessLoading.value = false;
    }
  }

  async function launchRun(payload: Parameters<typeof createRun>[1]) {
    return runSafely("发起并发评测", async () => {
      const created = await createRun(projectId.value, payload);
      runs.value = [created, ...runs.value];
      activeRun.value = created;
      notice.value = `评测批次 #${created.id.slice(0, 8)} 已入队（并发度 ${created.concurrency}）。`;
      return created;
    });
  }

  async function launchMatrixRun(
    payload: Parameters<typeof createMatrixRuns>[1],
  ) {
    return runSafely("发起矩阵打擂", async () => {
      const res = await createMatrixRuns(projectId.value, payload);
      runs.value = [...res.runs, ...runs.value];
      if (res.runs[0]) activeRun.value = res.runs[0];
      notice.value = `矩阵打擂已启动（共 ${res.runs.length} 组平行配置）。`;
      return res;
    });
  }

  async function openRun(runId: string) {
    return runSafely("读取批次详情", async () => {
      const detail = await getRunDetail(projectId.value, runId);
      activeRun.value = detail.run;
      runCases.value = detail.cases;
      return detail;
    });
  }

  async function pollRunningRuns() {
    if (!projectId.value) return;
    try {
      const latestRuns = await listRuns(projectId.value);
      runs.value = latestRuns;
      if (activeRun.value) {
        const detail = await getRunDetail(projectId.value, activeRun.value.id);
        activeRun.value = detail.run;
        runCases.value = detail.cases;
      }
    } catch {
      // Background polling swallows transient errors to avoid noisy banners.
    }
  }

  async function sendRunControl(
    runId: string,
    action: "pause" | "resume" | "retry_failed" | "rescore" | "cancel",
  ) {
    return runSafely("控制评测任务", async () => {
      const updated = await controlRun(projectId.value, runId, action);
      runs.value = runs.value.map((r) => (r.id === updated.id ? updated : r));
      if (activeRun.value?.id === updated.id) {
        const detail = await getRunDetail(projectId.value, runId);
        activeRun.value = detail.run;
        runCases.value = detail.cases;
      }
      return updated;
    });
  }

  async function removeRun(runId: string) {
    return runSafely("删除评测结果", async () => {
      await deleteRun(projectId.value, runId);
      runs.value = runs.value.filter((r) => r.id !== runId);
      if (activeRun.value?.id === runId) {
        activeRun.value = null;
        runCases.value = [];
      }
      notice.value = `评测记录 #${runId.slice(0, 8)} 已彻底删除。`;
      return true;
    });
  }

  async function fetchRunLogs(
    runId: string,
    params?: Parameters<typeof getRunLogs>[2],
  ) {
    if (!projectId.value) return null;
    return getRunLogs(projectId.value, runId, params);
  }

  async function loadComparison(baselineId: string, candidateId: string) {
    return runSafely("加载横向对比 PK", async () => {
      comparison.value = await compareRuns(
        projectId.value,
        baselineId,
        candidateId,
      );
      return comparison.value;
    });
  }

  async function reviewCase(
    runCaseId: string,
    verdict: "pass" | "fail",
    reason: string,
  ) {
    return runSafely("提交人工抽检标定", async () => {
      await submitHumanReview(projectId.value, runCaseId, {
        human_verdict: verdict,
        reason,
      });
      notice.value = `已提交人工抽检意见 (${verdict})。`;
      return true;
    });
  }

  async function addPatrol(payload: PatrolCreatePayload) {
    return runSafely("创建定时巡检", async () => {
      const created = await createPatrol(projectId.value, payload);
      patrols.value = await listPatrols(projectId.value);
      notice.value = `已创建定时巡检「${created.name}」。`;
      return created;
    });
  }

  async function editPatrol(scheduleId: string, payload: PatrolUpdatePayload) {
    return runSafely("更新定时巡检", async () => {
      const updated = await updatePatrol(projectId.value, scheduleId, payload);
      patrols.value = await listPatrols(projectId.value);
      notice.value = `已更新定时巡检「${updated.name}」。`;
      return updated;
    });
  }

  async function removePatrol(scheduleId: string) {
    return runSafely("删除定时巡检", async () => {
      await deletePatrol(projectId.value, scheduleId);
      patrols.value = patrols.value.filter((p) => p.id !== scheduleId);
      notice.value = "定时巡检配置已删除（历史巡检打擂记录已保留）。";
      return true;
    });
  }

  async function runPatrolNow(scheduleId: string) {
    return runSafely("立即触发巡检", async () => {
      const res = await triggerPatrol(projectId.value, scheduleId);
      const [patrolRows, runRows] = await Promise.all([
        listPatrols(projectId.value),
        listRuns(projectId.value),
      ]);
      patrols.value = patrolRows;
      runs.value = runRows;
      if (res.run) {
        await openRun(res.run.id);
      }
      notice.value = `巡检「${res.schedule?.name || ""}」已立即入队执行。`;
      return res;
    });
  }

  async function checkPatrolCron(
    cronExpr: string,
    timezone = "Asia/Shanghai",
    count = 5,
  ) {
    if (!projectId.value) return null;
    return previewPatrolCron(projectId.value, {
      cron_expr: cronExpr,
      timezone,
      count,
    });
  }

  async function toggleSandbox(isSandbox: boolean) {
    return runSafely("更新隔离靶场标记", async () => {
      const res = await setSandboxFlag(projectId.value, isSandbox);
      notice.value = res.is_sandbox
        ? "已将当前项目设为专用测试靶场。"
        : "已取消当前项目专用靶场标记。";
      return res;
    });
  }

  return {
    loading,
    busyAction,
    error,
    notice,
    suites,
    activeSuite,
    suiteCases,
    suiteVersions,
    runs,
    activeRun,
    runCases,
    patrols,
    readiness,
    readinessLoading,
    readinessError,
    comparison,
    totalCasesCount,
    publishedSuitesCount,
    refreshAll,
    openSuite,
    addSuite,
    removeSuite,
    convertSessionsToSuite,
    saveCase,
    importCasesBatch,
    removeCase,
    publishSuite,
    runReadiness,
    launchRun,
    launchMatrixRun,
    openRun,
    pollRunningRuns,
    sendRunControl,
    removeRun,
    fetchRunLogs,
    loadComparison,
    reviewCase,
    addPatrol,
    editPatrol,
    removePatrol,
    runPatrolNow,
    checkPatrolCron,
    toggleSandbox,
  };
}
