"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ListSearch } from "@/components/platform/list-search";
import { PageStateEmpty, PageStateError, PageStateLoading } from "@/components/platform/page-state";
import { DEFAULT_PAGE_SIZE_OPTIONS, PaginationControls } from "@/components/platform/pagination-controls";
import { TestcaseOverviewStrip } from "@/components/platform/testcase-overview-strip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getTestcaseDocument,
  getTestcaseOverview,
  listTestcaseBatches,
  listTestcaseDocuments,
  type TestcaseBatchSummary,
  type TestcaseDocument,
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

const PARSE_STATUS_OPTIONS = ["", "parsed", "failed", "unsupported", "unprocessed"];

export default function TestcaseDocumentsPage() {
  const { projectId } = useWorkspaceContext();
  const [overview, setOverview] = useState<TestcaseOverview | null>(null);
  const [batches, setBatches] = useState<TestcaseBatchSummary[]>([]);
  const [items, setItems] = useState<TestcaseDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [offset, setOffset] = useState(0);
  const [customPage, setCustomPage] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [batchFilter, setBatchFilter] = useState("");
  const [parseStatusFilter, setParseStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedItem, setSelectedItem] = useState<TestcaseDocument | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

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
      const payload = await listTestcaseDocuments(projectId, {
        batch_id: batchFilter || undefined,
        parse_status: parseStatusFilter || undefined,
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
      setError(err instanceof Error ? err.message : "Failed to load testcase documents");
    } finally {
      setLoading(false);
    }
  }, [batchFilter, offset, pageSize, parseStatusFilter, projectId, query]);

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
        const payload = await getTestcaseDocument(projectId, selectedId);
        if (!cancelled) {
          setSelectedItem(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setSelectedItem(null);
          setDetailError(err instanceof Error ? err.message : "Failed to load document detail");
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

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">PDF 解析</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        查看已保存到 `interaction-data-service` 的文档解析结果，重点回看 `parsed_text` 和结构化提取内容。
      </p>

      <TestcaseOverviewStrip overview={overview} />

      <div className="mt-4 flex flex-wrap items-center gap-2">
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
          解析状态
          <select
            className="ml-2 h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={parseStatusFilter}
            onChange={(event) => {
              setParseStatusFilter(event.target.value);
              setOffset(0);
            }}
          >
            {PARSE_STATUS_OPTIONS.map((item) => (
              <option key={item || "all"} value={item}>
                {item || "全部状态"}
              </option>
            ))}
          </select>
        </label>
      </div>

      <ListSearch
        value={searchInput}
        placeholder="按文件名或摘要搜索"
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

      {!projectId ? <PageStateEmpty message="当前没有选中项目，无法读取 PDF 解析结果。" /> : null}
      {projectId && loading ? <PageStateLoading message="Loading testcase documents..." /> : null}
      {projectId && error ? <PageStateError message={error} /> : null}

      {projectId && !loading && !error && items.length === 0 ? (
        <PageStateEmpty
          message={
            selectedBatchLabel
              ? `批次 ${selectedBatchLabel} 暂无文档解析结果。`
              : "当前项目下还没有保存过 PDF 解析结果。"
          }
        />
      ) : null}

      {projectId && !loading && !error && items.length > 0 ? (
        <>
          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,1fr)]">
            <div className="overflow-hidden rounded-xl border border-border">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-muted/40 text-left text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3">文件名</th>
                      <th className="px-4 py-3">状态</th>
                      <th className="px-4 py-3">来源</th>
                      <th className="px-4 py-3">批次</th>
                      <th className="px-4 py-3">创建时间</th>
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
                              <div className="font-medium text-foreground">{item.filename}</div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                {item.content_type}
                              </div>
                            </button>
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{item.parse_status}</td>
                          <td className="px-4 py-3 text-muted-foreground">{item.source_kind}</td>
                          <td className="px-4 py-3 text-muted-foreground">{item.batch_id || "-"}</td>
                          <td className="px-4 py-3 text-muted-foreground">{formatDateTime(item.created_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <Card className="gap-4 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">解析详情</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 px-4">
                {detailLoading ? <PageStateLoading message="Loading document detail..." className="mt-0" /> : null}
                {detailError ? <PageStateError message={detailError} className="mt-0" /> : null}
                {!detailLoading && !detailError && selectedItem ? (
                  <>
                    <div className="space-y-1">
                      <div className="text-lg font-semibold tracking-tight break-all">{selectedItem.filename}</div>
                      <div className="text-xs text-muted-foreground">{selectedItem.id}</div>
                    </div>
                    <dl className="grid gap-3 text-sm">
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">解析状态</dt>
                        <dd className="mt-1">{selectedItem.parse_status}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">批次</dt>
                        <dd className="mt-1 break-all">{selectedItem.batch_id || "-"}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">摘要</dt>
                        <dd className="mt-1 whitespace-pre-wrap text-muted-foreground">
                          {selectedItem.summary_for_model || "-"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">parsed_text</dt>
                        <dd className="mt-2">
                          {selectedItem.parsed_text ? (
                            <pre className="max-h-[260px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-6 whitespace-pre-wrap">
                              {selectedItem.parsed_text}
                            </pre>
                          ) : (
                            <div className="rounded-lg border border-dashed border-border bg-muted/20 p-3 text-xs leading-6 text-muted-foreground">
                              当前记录未保存 parsed_text。当前 parse_status=`{selectedItem.parse_status}`，
                              现阶段可回看摘要和 structured_data。
                            </div>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">structured_data</dt>
                        <dd className="mt-2">
                          <pre className="max-h-[220px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-6">
                            {stringifyJson(selectedItem.structured_data)}
                          </pre>
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">provenance</dt>
                        <dd className="mt-2">
                          <pre className="max-h-[180px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-6">
                            {stringifyJson(selectedItem.provenance)}
                          </pre>
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">error</dt>
                        <dd className="mt-2">
                          <pre className="max-h-[140px] overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-6">
                            {stringifyJson(selectedItem.error)}
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
