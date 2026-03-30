"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { ListSearch } from "@/components/platform/list-search";
import { PageStateEmpty, PageStateError, PageStateLoading } from "@/components/platform/page-state";
import { DEFAULT_PAGE_SIZE_OPTIONS, PaginationControls } from "@/components/platform/pagination-controls";
import { TestcaseOverviewStrip } from "@/components/platform/testcase-overview-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  exportTestcaseCasesExcel,
  getTestcaseCase,
  getTestcaseOverview,
  listTestcaseBatches,
  listTestcaseCases,
  type TestcaseBatchSummary,
  type TestcaseCase,
  type TestcaseOverview,
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

const STATUS_OPTIONS = ["", "active", "draft", "disabled", "archived"];

export default function TestcaseCasesPage() {
  const { projectId } = useWorkspaceContext();
  const [overview, setOverview] = useState<TestcaseOverview | null>(null);
  const [batches, setBatches] = useState<TestcaseBatchSummary[]>([]);
  const [items, setItems] = useState<TestcaseCase[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [offset, setOffset] = useState(0);
  const [customPage, setCustomPage] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [batchFilter, setBatchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedItem, setSelectedItem] = useState<TestcaseCase | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));

  const loadMeta = useCallback(async () => {
    if (!projectId) {
      setOverview(null);
      setBatches([]);
      return;
    }
    try {
      const [overviewPayload, batchesPayload] = await Promise.all([
        getTestcaseOverview(projectId),
        listTestcaseBatches(projectId, { limit: 100, offset: 0 }),
      ]);
      setOverview(overviewPayload);
      setBatches(batchesPayload.items);
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

  useEffect(() => {
    void loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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
  }, [projectId, selectedId]);

  const selectedBatchLabel = useMemo(
    () => batches.find((item) => item.batch_id === batchFilter)?.batch_id ?? "",
    [batchFilter, batches],
  );

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
  }, [batchFilter, exporting, projectId, query, statusFilter, total]);

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">用例管理</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        查看 `test_case_service` 正式保存的测试用例，按批次回看生成结果。
      </p>

      <TestcaseOverviewStrip overview={overview} />

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-muted-foreground">
            批次
            <select
              className="ml-2 h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={batchFilter}
              onChange={(event) => {
                setBatchFilter(event.target.value);
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

        <Button
          type="button"
          variant="outline"
          onClick={() => void handleExport()}
          disabled={!projectId || loading || exporting || total <= 0}
        >
          {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
          {exporting ? "导出中..." : "导出 Excel"}
        </Button>
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

      {projectId && !loading && !error && items.length === 0 ? (
        <PageStateEmpty
          message={
            selectedBatchLabel
              ? `批次 ${selectedBatchLabel} 暂无测试用例。`
              : "当前项目下还没有正式保存的测试用例。"
          }
        />
      ) : null}

      {projectId && !loading && !error && items.length > 0 ? (
        <>
          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)]">
            <div className="overflow-hidden rounded-xl border border-border">
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
                              onClick={() => setSelectedId(item.id)}
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
            </div>

            <Card className="gap-4 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">用例详情</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 px-4">
                {detailLoading ? <PageStateLoading message="Loading case detail..." className="mt-0" /> : null}
                {detailError ? <PageStateError message={detailError} className="mt-0" /> : null}
                {!detailLoading && !detailError && selectedItem ? (
                  <>
                    <div className="space-y-1">
                      <div className="text-lg font-semibold tracking-tight">{selectedItem.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {selectedItem.case_id || selectedItem.id}
                      </div>
                    </div>
                    <dl className="grid gap-3 text-sm">
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
                        <dd className="mt-1 whitespace-pre-wrap text-muted-foreground">
                          {selectedItem.description || "-"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">来源文档</dt>
                        <dd className="mt-1 break-all text-muted-foreground">
                          {selectedItem.source_document_ids.length > 0
                            ? selectedItem.source_document_ids.join(", ")
                            : "-"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">content_json</dt>
                        <dd className="mt-2">
                          <pre className="max-h-[420px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-6">
                            {stringifyJson(selectedItem.content_json)}
                          </pre>
                        </dd>
                      </div>
                    </dl>
                  </>
                ) : null}
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
    </section>
  );
}
