"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, Loader2, PencilLine, Plus, Settings2, Trash2 } from "lucide-react";
import { useQueryState } from "nuqs";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/platform/confirm-dialog";
import { ListSearch } from "@/components/platform/list-search";
import { PageStateEmpty, PageStateError, PageStateLoading } from "@/components/platform/page-state";
import { DEFAULT_PAGE_SIZE_OPTIONS, PaginationControls } from "@/components/platform/pagination-controls";
import { TestcaseWorkspaceNav } from "@/components/platform/testcase-chat-header";
import { TestcaseOverviewStrip } from "@/components/platform/testcase-overview-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  createTestcaseCase,
  deleteTestcaseCase,
  exportTestcaseCasesExcel,
  getTestcaseCase,
  getTestcaseOverview,
  getTestcaseRole,
  listTestcaseBatches,
  listTestcaseCases,
  listTestcaseDocuments,
  updateTestcaseCase,
  type TestcaseBatchSummary,
  type TestcaseCase,
  type TestcaseDocument,
  type TestcaseOverview,
  type TestcaseRole,
} from "@/lib/management-api/testcase";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function triggerBrowserDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function coerceText(value: unknown): string {
  if (value == null) {
    return "";
  }
  return String(value).trim();
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => coerceText(item))
    .filter(Boolean);
}

function joinLines(value: unknown): string {
  return asStringList(value).join("\n");
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseJsonObjectText(value: string): { value: Record<string, unknown>; error: string | null } {
  const normalized = value.trim();
  if (!normalized) {
    return { value: {}, error: null };
  }

  try {
    const parsed = JSON.parse(normalized) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {
        value: {},
        error: "test_data 必须是 JSON object，不能是数组或纯文本。",
      };
    }
    return { value: parsed as Record<string, unknown>, error: null };
  } catch (err) {
    return {
      value: {},
      error: err instanceof Error ? `test_data JSON 非法：${err.message}` : "test_data JSON 非法",
    };
  }
}

type EditorMode = "detail" | "create" | "edit";

type PendingEditorAction =
  | { type: "detail" }
  | { type: "create" }
  | { type: "edit" }
  | { type: "select"; id: string };

type CaseFormState = {
  batch_id: string;
  case_id: string;
  title: string;
  description: string;
  status: string;
  module_name: string;
  priority: string;
  source_document_ids: string[];
  preconditions_text: string;
  steps_text: string;
  expected_results_text: string;
  test_type: string;
  design_technique: string;
  test_data_text: string;
  remarks: string;
};

const STATUS_OPTIONS = ["", "active", "draft", "disabled", "archived"];
const FORM_STATUS_OPTIONS = ["active", "draft", "disabled", "archived"];
const PRIORITY_OPTIONS = ["", "P0", "P1", "P2", "P3", "高", "中", "低"];
const EXPORT_COLUMN_OPTIONS = [
  { key: "case_id", label: "Case ID" },
  { key: "title", label: "标题" },
  { key: "module_name", label: "模块" },
  { key: "priority", label: "优先级" },
  { key: "status", label: "状态" },
  { key: "description", label: "描述" },
  { key: "preconditions", label: "前置条件" },
  { key: "steps", label: "步骤" },
  { key: "expected_results", label: "预期结果" },
  { key: "test_type", label: "测试类型" },
  { key: "design_technique", label: "设计技术" },
  { key: "test_data", label: "测试数据" },
  { key: "remarks", label: "备注" },
  { key: "quality_gate", label: "质量门禁" },
  { key: "quality_score", label: "质量分数" },
  { key: "batch_id", label: "批次 ID" },
  { key: "source_document_ids", label: "来源文档 IDs" },
  { key: "created_at", label: "创建时间" },
  { key: "updated_at", label: "更新时间" },
] as const;
const DEFAULT_EXPORT_COLUMNS = EXPORT_COLUMN_OPTIONS.map((item) => item.key);
const STANDARD_EXPORT_COLUMNS = [
  "case_id",
  "title",
  "module_name",
  "priority",
  "status",
  "description",
  "steps",
  "expected_results",
  "batch_id",
  "updated_at",
];

function buildDefaultForm(batchId = ""): CaseFormState {
  return {
    batch_id: batchId,
    case_id: "",
    title: "",
    description: "",
    status: "active",
    module_name: "",
    priority: "",
    source_document_ids: [],
    preconditions_text: "",
    steps_text: "",
    expected_results_text: "",
    test_type: "",
    design_technique: "",
    test_data_text: "{}",
    remarks: "",
  };
}

function buildFormFromCase(item: TestcaseCase): CaseFormState {
  const content = asRecord(item.content_json);
  const testData = asRecord(content.test_data);
  return {
    batch_id: item.batch_id ?? "",
    case_id: item.case_id ?? coerceText(content.case_id),
    title: item.title,
    description: item.description,
    status: item.status,
    module_name: item.module_name ?? coerceText(content.module_name),
    priority: item.priority ?? coerceText(content.priority),
    source_document_ids: item.source_document_ids ?? [],
    preconditions_text: joinLines(content.preconditions),
    steps_text: joinLines(content.steps),
    expected_results_text: joinLines(content.expected_results),
    test_type: coerceText(content.test_type),
    design_technique: coerceText(content.design_technique),
    test_data_text: Object.keys(testData).length > 0 ? stringifyJson(testData) : "{}",
    remarks: coerceText(content.remarks),
  };
}

function buildContentJsonPayload(form: CaseFormState, baseContentJson?: Record<string, unknown>) {
  const next: Record<string, unknown> = { ...(baseContentJson ?? {}) };
  const assign = (key: string, value: unknown) => {
    if (value == null) {
      delete next[key];
      return;
    }
    if (typeof value === "string" && value.trim() === "") {
      delete next[key];
      return;
    }
    if (Array.isArray(value) && value.length === 0) {
      delete next[key];
      return;
    }
    if (typeof value === "object" && !Array.isArray(value) && Object.keys(asRecord(value)).length === 0) {
      delete next[key];
      return;
    }
    next[key] = value;
  };

  assign("case_id", form.case_id);
  assign("title", form.title);
  assign("description", form.description);
  assign("module_name", form.module_name);
  assign("priority", form.priority);
  assign("preconditions", splitLines(form.preconditions_text));
  assign("steps", splitLines(form.steps_text));
  assign("expected_results", splitLines(form.expected_results_text));
  assign("test_type", form.test_type);
  assign("design_technique", form.design_technique);
  assign("remarks", form.remarks);

  const parsedTestData = parseJsonObjectText(form.test_data_text);
  if (parsedTestData.error) {
    throw new Error(parsedTestData.error);
  }
  assign("test_data", parsedTestData.value);

  return next;
}

export default function TestcaseCasesPage() {
  const { projectId } = useWorkspaceContext();
  const [batchQuery, setBatchQuery] = useQueryState("batchId", { defaultValue: "" });
  const [overview, setOverview] = useState<TestcaseOverview | null>(null);
  const [batches, setBatches] = useState<TestcaseBatchSummary[]>([]);
  const [items, setItems] = useState<TestcaseCase[]>([]);
  const [documents, setDocuments] = useState<TestcaseDocument[]>([]);
  const [role, setRole] = useState<TestcaseRole | null>(null);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [offset, setOffset] = useState(0);
  const [customPage, setCustomPage] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [batchFilter, setBatchFilter] = useState(batchQuery);
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedItem, setSelectedItem] = useState<TestcaseCase | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [editorMode, setEditorMode] = useState<EditorMode>("detail");
  const [form, setForm] = useState<CaseFormState>(buildDefaultForm());
  const [initialForm, setInitialForm] = useState<CaseFormState>(buildDefaultForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [saveAttempted, setSaveAttempted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [sourceDocumentQuery, setSourceDocumentQuery] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const [pendingEditorAction, setPendingEditorAction] = useState<PendingEditorAction | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [showExportConfig, setShowExportConfig] = useState(false);
  const [exportColumns, setExportColumns] = useState<string[]>(DEFAULT_EXPORT_COLUMNS);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const canWrite = Boolean(role?.can_write_testcase);
  const selectedBatchLabel = useMemo(
    () => batches.find((item) => item.batch_id === batchFilter)?.batch_id ?? "",
    [batchFilter, batches],
  );
  const parsedTestData = useMemo(() => parseJsonObjectText(form.test_data_text), [form.test_data_text]);
  const stepsCount = useMemo(() => splitLines(form.steps_text).length, [form.steps_text]);
  const expectedResultsCount = useMemo(
    () => splitLines(form.expected_results_text).length,
    [form.expected_results_text],
  );
  const preconditionsCount = useMemo(() => splitLines(form.preconditions_text).length, [form.preconditions_text]);
  const isFormDirty = useMemo(
    () => editorMode !== "detail" && JSON.stringify(form) !== JSON.stringify(initialForm),
    [editorMode, form, initialForm],
  );
  const sourceDocumentLookup = useMemo(
    () => new Map(documents.map((item) => [item.id, item])),
    [documents],
  );
  const visibleDocuments = useMemo(() => {
    const normalized = sourceDocumentQuery.trim().toLowerCase();
    if (!normalized) {
      return documents;
    }
    return documents.filter((document) =>
      [document.filename, document.id, document.parse_status, document.batch_id]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized)),
    );
  }, [documents, sourceDocumentQuery]);
  const selectedSourceDocuments = useMemo(
    () =>
      form.source_document_ids
        .map((documentId) => sourceDocumentLookup.get(documentId) ?? null)
        .filter((item): item is TestcaseDocument => Boolean(item)),
    [form.source_document_ids, sourceDocumentLookup],
  );
  const unresolvedSourceDocumentIds = useMemo(
    () => form.source_document_ids.filter((documentId) => !sourceDocumentLookup.has(documentId)),
    [form.source_document_ids, sourceDocumentLookup],
  );

  useEffect(() => {
    const normalized = batchQuery ?? "";
    setBatchFilter((current) => (current === normalized ? current : normalized));
  }, [batchQuery]);

  const loadMeta = useCallback(async () => {
    if (!projectId) {
      setOverview(null);
      setBatches([]);
      setRole(null);
      return;
    }
    try {
      const [overviewPayload, batchesPayload, rolePayload] = await Promise.all([
        getTestcaseOverview(projectId),
        listTestcaseBatches(projectId, { limit: 100, offset: 0 }),
        getTestcaseRole(projectId),
      ]);
      setOverview(overviewPayload);
      setBatches(batchesPayload.items);
      setRole(rolePayload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load testcase metadata");
    }
  }, [projectId]);

  const refresh = useCallback(async () => {
    if (!projectId) {
      setItems([]);
      setTotal(0);
      setSelectedId("");
      setSelectedItem(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await listTestcaseCases(projectId, {
        batch_id: batchFilter || undefined,
        status: statusFilter || undefined,
        query: query || undefined,
        limit: pageSize,
        offset,
      });
      setItems(payload.items);
      setTotal(payload.total);
      if (payload.total > 0 && offset >= payload.total) {
        const fallbackOffset = Math.max(0, (Math.ceil(payload.total / pageSize) - 1) * pageSize);
        if (fallbackOffset !== offset) {
          setOffset(fallbackOffset);
          return;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load testcase cases");
    } finally {
      setLoading(false);
    }
  }, [batchFilter, offset, pageSize, projectId, query, statusFilter]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadMeta(), refresh()]);
  }, [loadMeta, refresh]);

  const normalizeMutationError = useCallback(
    async (message: string) => {
      if (message.includes("forbidden")) {
        await loadMeta();
        return "当前角色无写权限，权限状态已刷新。";
      }
      if (message.includes("not_found")) {
        setEditorMode("detail");
        await refreshAll();
        return "当前测试用例不存在，列表已刷新。";
      }
      return message;
    },
    [loadMeta, refreshAll],
  );

  const loadSourceDocuments = useCallback(async () => {
    if (!projectId || editorMode === "detail") {
      setDocuments([]);
      return;
    }
    setDocumentsLoading(true);
    try {
      const payload = await listTestcaseDocuments(projectId, {
        batch_id: form.batch_id || batchFilter || undefined,
        limit: 200,
        offset: 0,
      });
      setDocuments(payload.items);
    } catch (err) {
      toast("加载来源文档失败", {
        description: err instanceof Error ? err.message : "Failed to load testcase documents",
      });
      setDocuments([]);
    } finally {
      setDocumentsLoading(false);
    }
  }, [batchFilter, editorMode, form.batch_id, projectId]);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void loadSourceDocuments();
  }, [loadSourceDocuments]);

  useEffect(() => {
    setCustomPage(String(currentPage));
  }, [currentPage]);

  useEffect(() => {
    if (items.length === 0) {
      setSelectedId("");
      setSelectedItem(null);
      return;
    }
    if (!selectedId || !items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  useEffect(() => {
    if (editorMode !== "detail") {
      return;
    }
    if (!projectId || !selectedId) {
      setSelectedItem(null);
      setDetailError(null);
      return;
    }
    let cancelled = false;

    async function loadDetail() {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const payload = await getTestcaseCase(projectId, selectedId);
        if (!cancelled) {
          setSelectedItem(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setSelectedItem(null);
          setDetailError(err instanceof Error ? err.message : "Failed to load testcase detail");
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      cancelled = true;
    };
  }, [editorMode, projectId, selectedId]);

  const applyEditorAction = useCallback(
    (action: PendingEditorAction) => {
      switch (action.type) {
        case "detail":
          setEditorMode("detail");
          setFormError(null);
          setSaveAttempted(false);
          setSourceDocumentQuery("");
          setPendingEditorAction(null);
          return;
        case "select":
          setSelectedId(action.id);
          setEditorMode("detail");
          setFormError(null);
          setSaveAttempted(false);
          setSourceDocumentQuery("");
          setPendingEditorAction(null);
          return;
        case "create": {
          if (!canWrite) {
            toast("当前角色只读", { description: "只有 admin / editor 可以新增测试用例。" });
            return;
          }
          const nextForm = buildDefaultForm(batchFilter);
          setForm(nextForm);
          setInitialForm(nextForm);
          setFormError(null);
          setSaveAttempted(false);
          setSourceDocumentQuery("");
          setEditorMode("create");
          setPendingEditorAction(null);
          return;
        }
        case "edit": {
          if (!canWrite) {
            toast("当前角色只读", { description: "只有 admin / editor 可以编辑测试用例。" });
            return;
          }
          if (!selectedItem) {
            return;
          }
          const nextForm = buildFormFromCase(selectedItem);
          setForm(nextForm);
          setInitialForm(nextForm);
          setFormError(null);
          setSaveAttempted(false);
          setSourceDocumentQuery("");
          setEditorMode("edit");
          setPendingEditorAction(null);
        }
      }
    },
    [batchFilter, canWrite, selectedItem],
  );

  const requestEditorAction = useCallback(
    (action: PendingEditorAction) => {
      if (editorMode !== "detail" && isFormDirty) {
        setPendingEditorAction(action);
        setShowDiscardConfirm(true);
        return;
      }
      applyEditorAction(action);
    },
    [applyEditorAction, editorMode, isFormDirty],
  );

  const openCreateEditor = useCallback(() => {
    requestEditorAction({ type: "create" });
  }, [requestEditorAction]);

  const openEditEditor = useCallback(() => {
    requestEditorAction({ type: "edit" });
  }, [requestEditorAction]);

  const handleSave = useCallback(async () => {
    if (!projectId) {
      return;
    }
    if (!canWrite) {
      toast("当前角色只读", { description: "只有 admin / editor 可以保存测试用例。" });
      return;
    }
    setSaveAttempted(true);
    if (!form.title.trim()) {
      setFormError("标题不能为空");
      return;
    }
    if (stepsCount === 0) {
      setFormError("步骤至少填写 1 条。");
      return;
    }
    if (expectedResultsCount === 0) {
      setFormError("预期结果至少填写 1 条。");
      return;
    }
    if (parsedTestData.error) {
      setFormError(parsedTestData.error);
      return;
    }

    let contentJson: Record<string, unknown>;
    try {
      contentJson = buildContentJsonPayload(form, asRecord(selectedItem?.content_json));
    } catch (err) {
      setFormError(err instanceof Error ? `test_data JSON 非法：${err.message}` : "test_data JSON 非法");
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        batch_id: form.batch_id,
        case_id: form.case_id,
        title: form.title.trim(),
        description: form.description,
        status: form.status,
        module_name: form.module_name,
        priority: form.priority,
        source_document_ids: form.source_document_ids,
        content_json: contentJson,
      };
      const response =
        editorMode === "create"
          ? await createTestcaseCase(projectId, payload)
          : await updateTestcaseCase(projectId, selectedId, payload);
      toast(editorMode === "create" ? "创建成功" : "保存成功", {
        description: `${response.title} 已写回当前项目。`,
      });
      setEditorMode("detail");
      setInitialForm(buildFormFromCase(response));
      setSaveAttempted(false);
      setSourceDocumentQuery("");
      await refreshAll();
      setSelectedId(response.id);
      setSelectedItem(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save testcase";
      const normalizedMessage = await normalizeMutationError(message);
      setFormError(normalizedMessage);
      toast("保存失败", { description: normalizedMessage });
    } finally {
      setSaving(false);
    }
  }, [
    canWrite,
    editorMode,
    expectedResultsCount,
    form,
    normalizeMutationError,
    parsedTestData.error,
    projectId,
    refreshAll,
    selectedId,
    selectedItem,
    stepsCount,
  ]);

  const handleDelete = useCallback(async () => {
    if (!projectId || !selectedItem) {
      return;
    }
    setDeleting(true);
    try {
      await deleteTestcaseCase(projectId, selectedItem.id);
      toast("删除成功", {
        description: `${selectedItem.title} 已从当前项目移除。`,
      });
      setShowDeleteConfirm(false);
      setEditorMode("detail");
      setSelectedItem(null);
      await refreshAll();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete testcase case";
      const normalizedMessage = await normalizeMutationError(message);
      toast("删除失败", {
        description: normalizedMessage,
      });
    } finally {
      setDeleting(false);
    }
  }, [normalizeMutationError, projectId, refreshAll, selectedItem]);

  const handleExport = useCallback(async () => {
    if (!projectId || exporting) {
      return;
    }
    setExporting(true);
    try {
      const download = await exportTestcaseCasesExcel(projectId, {
        batch_id: batchFilter || undefined,
        status: statusFilter || undefined,
        query: query || undefined,
        columns: exportColumns,
      });
      const fallbackName = `testcase-cases-${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}.xlsx`;
      triggerBrowserDownload(download.blob, download.filename || fallbackName);
      toast("导出成功", {
        description: `已导出当前筛选结果，共 ${total} 条测试用例。`,
      });
    } catch (err) {
      toast("导出失败", {
        description: err instanceof Error ? err.message : "Failed to export testcase cases",
      });
    } finally {
      setExporting(false);
    }
  }, [batchFilter, exportColumns, exporting, projectId, query, statusFilter, total]);

  const detailMeta = useMemo(() => asRecord(asRecord(selectedItem?.content_json).meta), [selectedItem]);
  const titleError = saveAttempted && !form.title.trim() ? "标题不能为空。" : null;
  const stepsError = saveAttempted && stepsCount === 0 ? "步骤至少填写 1 条。" : null;
  const expectedResultsError =
    saveAttempted && expectedResultsCount === 0 ? "预期结果至少填写 1 条。" : null;
  const selectedSourceCount = form.source_document_ids.length;
  const detailSourceDocuments = selectedItem?.source_documents ?? [];
  const detailMissingSourceDocumentIds = selectedItem?.missing_source_document_ids ?? [];

  return (
    <section className="p-4 sm:p-6">
      <div className="mb-4">
        <TestcaseWorkspaceNav />
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">用例管理</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            查看 `test_case_service` 正式保存的测试用例，按批次回看生成结果，并支持人工补录与修订。
          </p>
          <p className="text-muted-foreground mt-2 text-xs">
            当前角色：{role?.role ?? "-"}；{canWrite ? "可写" : "只读"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" onClick={() => setShowExportConfig((value) => !value)}>
            <Settings2 className="size-4" />
            导出配置
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleExport()}
            disabled={!projectId || loading || exporting || total <= 0}
          >
            {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
            {exporting ? "导出中..." : "导出 Excel"}
          </Button>
          <Button type="button" onClick={openCreateEditor} disabled={!projectId || !canWrite}>
            <Plus className="size-4" />
            新增用例
          </Button>
        </div>
      </div>

      <TestcaseOverviewStrip overview={overview} />

      {showExportConfig ? (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">导出列配置</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setExportColumns(STANDARD_EXPORT_COLUMNS)}>
                标准列
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setExportColumns(DEFAULT_EXPORT_COLUMNS)}>
                完整列
              </Button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {EXPORT_COLUMN_OPTIONS.map((item) => {
                const checked = exportColumns.includes(item.key);
                return (
                  <label key={item.key} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) => {
                        setExportColumns((current) => {
                          if (event.target.checked) {
                            return current.includes(item.key) ? current : [...current, item.key];
                          }
                          const next = current.filter((value) => value !== item.key);
                          return next.length > 0 ? next : current;
                        });
                      }}
                    />
                    <span>{item.label}</span>
                  </label>
                );
              })}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted-foreground">
            批次
            <select
              className="ml-2 h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={batchFilter}
              onChange={(event) => {
                const nextValue = event.target.value;
                setBatchFilter(nextValue);
                void setBatchQuery(nextValue || null);
                setOffset(0);
              }}
            >
              <option value="">全部批次</option>
              {batches.map((item) => (
                <option key={item.batch_id} value={item.batch_id}>
                  {item.batch_id}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm text-muted-foreground">
            状态
            <select
              className="ml-2 h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setOffset(0);
              }}
            >
              {STATUS_OPTIONS.map((item) => (
                <option key={item || "all"} value={item}>
                  {item || "全部状态"}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <ListSearch
        value={searchInput}
        placeholder="按标题、模块、描述、case_id 搜索"
        onValueChange={setSearchInput}
        onSearch={(keyword) => {
          setQuery(keyword);
          setOffset(0);
        }}
        onClear={() => {
          setQuery("");
          setOffset(0);
        }}
      />

      {!projectId ? <PageStateEmpty message="当前没有选中项目，无法读取 testcase 数据。" /> : null}
      {projectId && loading ? <PageStateLoading message="Loading testcase cases..." /> : null}
      {projectId && error ? <PageStateError message={error} /> : null}

      {projectId && !loading && !error && items.length === 0 && editorMode === "detail" ? (
        <PageStateEmpty
          message={
            selectedBatchLabel
              ? `批次 ${selectedBatchLabel} 暂无测试用例。`
              : "当前项目下还没有正式保存的测试用例。"
          }
        />
      ) : null}

      {projectId && !loading && !error && (items.length > 0 || editorMode !== "detail") ? (
        <>
          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,1fr)]">
            <div className="overflow-hidden rounded-xl border border-border">
              {items.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-muted/40 text-left text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3">标题</th>
                        <th className="px-4 py-3">模块</th>
                        <th className="px-4 py-3">优先级</th>
                        <th className="px-4 py-3">状态</th>
                        <th className="px-4 py-3">批次</th>
                        <th className="px-4 py-3">更新时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => {
                        const active = item.id === selectedId;
                        return (
                          <tr
                            key={item.id}
                            className={[
                              "border-t border-border transition-colors",
                              active ? "bg-sidebar-primary/10" : "hover:bg-muted/30",
                            ].join(" ")}
                          >
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                className="text-left"
                                onClick={() => {
                                  requestEditorAction({ type: "select", id: item.id });
                                }}
                              >
                                <div className="font-medium text-foreground">{item.title}</div>
                                <div className="mt-1 text-xs text-muted-foreground">{item.case_id || item.id}</div>
                              </button>
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">{item.module_name || "-"}</td>
                            <td className="px-4 py-3 text-muted-foreground">{item.priority || "-"}</td>
                            <td className="px-4 py-3 text-muted-foreground">{item.status}</td>
                            <td className="px-4 py-3 text-muted-foreground">{item.batch_id || "-"}</td>
                            <td className="px-4 py-3 text-muted-foreground">{formatDateTime(item.updated_at)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="flex min-h-[220px] items-center justify-center px-6 py-10 text-sm text-muted-foreground">
                  当前项目下还没有正式保存的测试用例，可以直接在右侧创建第一条记录。
                </div>
              )}
            </div>

            <Card className="min-w-0 gap-4 py-4">
              <CardHeader className="px-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="text-base">
                    {editorMode === "create" ? "新增用例" : editorMode === "edit" ? "编辑用例" : "用例详情"}
                  </CardTitle>
                  {editorMode === "detail" && selectedItem ? (
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="outline" size="sm" onClick={openEditEditor} disabled={!canWrite}>
                        <PencilLine className="size-4" />
                        编辑
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(true)}
                        disabled={!canWrite}
                      >
                        <Trash2 className="size-4" />
                        删除
                      </Button>
                    </div>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="space-y-4 px-4">
                {editorMode === "detail" ? (
                  <>
                    {detailLoading ? <PageStateLoading message="Loading case detail..." className="mt-0" /> : null}
                    {detailError ? <PageStateError message={detailError} className="mt-0" /> : null}
                    {!detailLoading && !detailError && selectedItem ? (
                      <>
                        <div className="space-y-1">
                          <div className="text-lg font-semibold tracking-tight">{selectedItem.title}</div>
                          <div className="text-xs text-muted-foreground">{selectedItem.case_id || selectedItem.id}</div>
                        </div>
                        <dl className="min-w-0 grid gap-3 text-sm">
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">状态</dt>
                            <dd className="mt-1">{selectedItem.status}</dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">模块</dt>
                            <dd className="mt-1">{selectedItem.module_name || "-"}</dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">优先级</dt>
                            <dd className="mt-1">{selectedItem.priority || "-"}</dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">批次</dt>
                            <dd className="mt-1 break-all">{selectedItem.batch_id || "-"}</dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">描述</dt>
                            <dd className="mt-1 whitespace-pre-wrap text-muted-foreground">{selectedItem.description || "-"}</dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">来源文档</dt>
                            <dd className="mt-2 space-y-2 text-muted-foreground">
                              {detailSourceDocuments.length > 0 ? (
                                detailSourceDocuments.map((document) => (
                                  <div key={document.id} className="max-w-full rounded-md border border-border bg-muted/20 px-3 py-2 text-xs">
                                    <div className="font-medium text-foreground break-all">{document.filename}</div>
                                    <div className="mt-1 text-muted-foreground break-all">{document.id}</div>
                                    <div className="mt-1 text-muted-foreground">
                                      {document.parse_status} / {document.batch_id || "-"} / {formatDateTime(document.created_at)}
                                    </div>
                                  </div>
                                ))
                              ) : (
                                "-"
                              )}
                              {detailMissingSourceDocumentIds.length > 0 ? (
                                <div className="rounded-md border border-dashed border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                                  以下来源文档当前无法解析详情，保留原始 ID：
                                  <div className="mt-2 space-y-1">
                                    {detailMissingSourceDocumentIds.map((documentId) => (
                                      <div key={documentId} className="break-all">{documentId}</div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">质量评审</dt>
                            <dd className="mt-2">
                              <pre className="max-h-[160px] max-w-full overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-3 text-xs leading-6">
                                {stringifyJson(detailMeta.quality_review)}
                              </pre>
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">content_json</dt>
                            <dd className="mt-2">
                              <pre className="max-h-[320px] max-w-full overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-3 text-xs leading-6">
                                {stringifyJson(selectedItem.content_json)}
                              </pre>
                            </dd>
                          </div>
                        </dl>
                      </>
                    ) : null}
                  </>
                ) : (
                  <div className="space-y-4">
                    <div className="space-y-4 rounded-xl border border-border/80 bg-muted/10 p-4">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold tracking-tight">基础信息</div>
                        <div className="text-xs text-muted-foreground">维护批次、标题、模块、优先级等主索引字段。</div>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="case-batch-id">批次 ID</Label>
                          <Input
                            id="case-batch-id"
                            value={form.batch_id}
                            onChange={(event) => setForm((current) => ({ ...current, batch_id: event.target.value }))}
                            placeholder="可为空，默认沿用当前筛选批次"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="case-case-id">Case ID</Label>
                          <Input
                            id="case-case-id"
                            value={form.case_id}
                            onChange={(event) => setForm((current) => ({ ...current, case_id: event.target.value }))}
                            placeholder="例如 TC-LOGIN-001"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="case-title">标题</Label>
                        <Input
                          id="case-title"
                          value={form.title}
                          onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                          placeholder="请输入测试用例标题"
                        />
                        {titleError ? <div className="text-xs text-destructive">{titleError}</div> : null}
                      </div>

                      <div className="grid gap-4 sm:grid-cols-3">
                        <div className="space-y-2">
                          <Label htmlFor="case-status">状态</Label>
                          <select
                            id="case-status"
                            className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm"
                            value={form.status}
                            onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}
                          >
                            {FORM_STATUS_OPTIONS.map((item) => (
                              <option key={item} value={item}>
                                {item}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="case-module">模块</Label>
                          <Input
                            id="case-module"
                            value={form.module_name}
                            onChange={(event) => setForm((current) => ({ ...current, module_name: event.target.value }))}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="case-priority">优先级</Label>
                          <select
                            id="case-priority"
                            className="h-10 w-full rounded-md border border-border bg-background px-3 text-sm"
                            value={form.priority}
                            onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value }))}
                          >
                            {PRIORITY_OPTIONS.map((item) => (
                              <option key={item || "empty"} value={item}>
                                {item || "未设置"}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4 rounded-xl border border-border/80 bg-muted/10 p-4">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold tracking-tight">用例正文</div>
                        <div className="text-xs text-muted-foreground">用一行一项的方式维护步骤和预期，减少保存时再返工。</div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="case-description">描述</Label>
                        <Textarea
                          id="case-description"
                          value={form.description}
                          onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                          rows={4}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="case-preconditions">前置条件（一行一项，当前 {preconditionsCount} 条）</Label>
                        <Textarea
                          id="case-preconditions"
                          value={form.preconditions_text}
                          onChange={(event) => setForm((current) => ({ ...current, preconditions_text: event.target.value }))}
                          rows={4}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="case-steps">步骤（一行一项，当前 {stepsCount} 条）</Label>
                        <Textarea
                          id="case-steps"
                          value={form.steps_text}
                          onChange={(event) => setForm((current) => ({ ...current, steps_text: event.target.value }))}
                          rows={6}
                        />
                        {stepsError ? <div className="text-xs text-destructive">{stepsError}</div> : null}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="case-expected-results">预期结果（一行一项，当前 {expectedResultsCount} 条）</Label>
                        <Textarea
                          id="case-expected-results"
                          value={form.expected_results_text}
                          onChange={(event) => setForm((current) => ({ ...current, expected_results_text: event.target.value }))}
                          rows={5}
                        />
                        {expectedResultsError ? <div className="text-xs text-destructive">{expectedResultsError}</div> : null}
                      </div>
                    </div>

                    <div className="space-y-4 rounded-xl border border-border/80 bg-muted/10 p-4">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold tracking-tight">扩展信息</div>
                        <div className="text-xs text-muted-foreground">补充测试类型、设计技术、JSON 测试数据与备注。</div>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label htmlFor="case-test-type">测试类型</Label>
                          <Input
                            id="case-test-type"
                            value={form.test_type}
                            onChange={(event) => setForm((current) => ({ ...current, test_type: event.target.value }))}
                            placeholder="例如 functional"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="case-design-technique">设计技术</Label>
                          <Input
                            id="case-design-technique"
                            value={form.design_technique}
                            onChange={(event) => setForm((current) => ({ ...current, design_technique: event.target.value }))}
                            placeholder="例如 boundary value"
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="case-test-data">测试数据（JSON object）</Label>
                        <Textarea
                          id="case-test-data"
                          value={form.test_data_text}
                          onChange={(event) => setForm((current) => ({ ...current, test_data_text: event.target.value }))}
                          rows={6}
                        />
                        <div className={parsedTestData.error ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>
                          {parsedTestData.error || "实时校验通过，保存时会按 JSON object 写入 content_json.test_data。"}
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="case-remarks">备注</Label>
                        <Textarea
                          id="case-remarks"
                          value={form.remarks}
                          onChange={(event) => setForm((current) => ({ ...current, remarks: event.target.value }))}
                          rows={3}
                        />
                      </div>

                      {editorMode === "edit" && selectedItem ? (
                        <>
                          <Separator />
                          <div className="space-y-3">
                            <div className="text-sm font-semibold tracking-tight">只读元信息</div>
                            <div className="grid gap-3 text-sm sm:grid-cols-2">
                              <div>
                                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">创建时间</div>
                                <div className="mt-1">{formatDateTime(selectedItem.created_at)}</div>
                              </div>
                              <div>
                                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">更新时间</div>
                                <div className="mt-1">{formatDateTime(selectedItem.updated_at)}</div>
                              </div>
                              <div>
                                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">bundle_title</div>
                                <div className="mt-1 break-all">{coerceText(detailMeta.bundle_title) || "-"}</div>
                              </div>
                              <div>
                                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">bundle_summary</div>
                                <div className="mt-1 whitespace-pre-wrap text-muted-foreground">{coerceText(detailMeta.bundle_summary) || "-"}</div>
                              </div>
                            </div>
                            <div>
                              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">quality_review</div>
                              <pre className="mt-2 max-h-[180px] max-w-full overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-3 text-xs leading-6">
                                {stringifyJson(detailMeta.quality_review)}
                              </pre>
                            </div>
                          </div>
                        </>
                      ) : null}
                    </div>

                    <div className="space-y-4 rounded-xl border border-border/80 bg-muted/10 p-4">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold tracking-tight">来源文档</div>
                        <div className="text-xs text-muted-foreground">
                          已选 {selectedSourceCount} 条，当前加载 {documents.length} 条，可按文件名、解析状态或文档 ID 搜索。
                        </div>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                        <Input
                          value={sourceDocumentQuery}
                          onChange={(event) => setSourceDocumentQuery(event.target.value)}
                          placeholder="搜索来源文档：文件名 / 解析状态 / document id"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => setSourceDocumentQuery("")}
                          disabled={sourceDocumentQuery.length === 0}
                        >
                          清空搜索
                        </Button>
                      </div>

                      {selectedSourceDocuments.length > 0 ? (
                        <div className="rounded-lg border border-border bg-background p-3">
                          <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">已选来源文档</div>
                          <div className="space-y-2">
                            {selectedSourceDocuments.map((document) => (
                              <div key={document.id} className="rounded-md border border-border/80 bg-muted/20 px-3 py-2 text-sm">
                                <div className="font-medium text-foreground">{document.filename}</div>
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {document.parse_status} / {document.batch_id || "-"} / {formatDateTime(document.created_at)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      {unresolvedSourceDocumentIds.length > 0 ? (
                        <div className="rounded-lg border border-dashed border-border bg-background p-3 text-xs text-muted-foreground">
                          以下来源文档当前未加载到列表中，但仍会随表单保存：
                          <div className="mt-2 space-y-1">
                            {unresolvedSourceDocumentIds.map((documentId) => (
                              <div key={documentId} className="break-all">{documentId}</div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      <div className="max-h-[280px] overflow-auto rounded-lg border border-border bg-muted/20 p-3">
                        {documentsLoading ? <div className="text-sm text-muted-foreground">Loading documents...</div> : null}
                        {!documentsLoading && documents.length === 0 ? (
                          <div className="text-sm text-muted-foreground">当前筛选批次下没有可关联的 document。</div>
                        ) : null}
                        {!documentsLoading && documents.length > 0 ? (
                          <div className="space-y-2">
                            {visibleDocuments.length > 0 ? (
                              visibleDocuments.map((document) => {
                                const checked = form.source_document_ids.includes(document.id);
                                return (
                                  <label
                                    key={document.id}
                                    className={[
                                      "flex items-start gap-3 rounded-md border px-3 py-3 text-sm transition-colors",
                                      checked
                                        ? "border-sidebar-primary/50 bg-sidebar-primary/10"
                                        : "border-border bg-background hover:bg-muted/20",
                                    ].join(" ")}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={(event) => {
                                        setForm((current) => ({
                                          ...current,
                                          source_document_ids: event.target.checked
                                            ? Array.from(new Set([...current.source_document_ids, document.id]))
                                            : current.source_document_ids.filter((item) => item !== document.id),
                                        }));
                                      }}
                                    />
                                    <span className="min-w-0 flex-1">
                                      <span className="block truncate font-medium text-foreground">{document.filename}</span>
                                      <span className="mt-1 block text-xs text-muted-foreground break-all">{document.id}</span>
                                      <span className="mt-1 block text-xs text-muted-foreground">
                                        {document.parse_status} / {document.batch_id || "-"} / {formatDateTime(document.created_at)}
                                      </span>
                                    </span>
                                  </label>
                                );
                              })
                            ) : (
                              <div className="text-sm text-muted-foreground">没有匹配当前搜索词的来源文档。</div>
                            )}
                          </div>
                        ) : null}
                      </div>
                    </div>

                    {formError ? (
                      <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                        {formError}
                      </div>
                    ) : null}

                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => requestEditorAction({ type: "detail" })}
                        disabled={saving}
                      >
                        取消
                      </Button>
                      <Button type="button" onClick={() => void handleSave()} disabled={saving}>
                        {saving ? <Loader2 className="size-4 animate-spin" /> : null}
                        {editorMode === "create" ? "创建并保存" : "保存修改"}
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <PaginationControls
            total={total}
            offset={offset}
            pageSize={pageSize}
            customPage={customPage}
            currentPage={currentPage}
            maxPage={maxPage}
            loading={loading}
            pageSizeOptions={DEFAULT_PAGE_SIZE_OPTIONS}
            onPageSizeChange={(next) => {
              setPageSize(next);
              setOffset(0);
            }}
            onCustomPageChange={setCustomPage}
            onApplyCustomPage={() => {
              const nextPage = Math.min(Math.max(1, Number(customPage) || 1), maxPage);
              setOffset((nextPage - 1) * pageSize);
            }}
            onPrevious={() => setOffset((current) => Math.max(0, current - pageSize))}
            onNext={() => setOffset((current) => current + pageSize)}
            previousDisabled={loading || offset <= 0}
            nextDisabled={loading || currentPage >= maxPage}
          />
        </>
      ) : null}

      <ConfirmDialog
        open={showDeleteConfirm}
        title="确认删除当前测试用例？"
        description={
          selectedItem ? (
            <div className="space-y-1">
              <div>标题：{selectedItem.title}</div>
              <div>Case ID：{selectedItem.case_id || selectedItem.id}</div>
              <div>批次：{selectedItem.batch_id || "-"}</div>
            </div>
          ) : undefined
        }
        confirmLabel="确认删除"
        confirmLabelLoading="删除中..."
        cancelLabel="取消"
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setShowDeleteConfirm(false)}
      />

      <ConfirmDialog
        open={showDiscardConfirm}
        title="存在未保存修改，确认离开？"
        description="当前表单还有未保存内容。继续切换会丢失这些修改。"
        confirmLabel="放弃修改"
        confirmLabelLoading="处理中..."
        cancelLabel="继续编辑"
        onConfirm={() => {
          setShowDiscardConfirm(false);
          if (pendingEditorAction) {
            applyEditorAction(pendingEditorAction);
          }
        }}
        onCancel={() => {
          setShowDiscardConfirm(false);
          setPendingEditorAction(null);
        }}
      />
    </section>
  );
}
