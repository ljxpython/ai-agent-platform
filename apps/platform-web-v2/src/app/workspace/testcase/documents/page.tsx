"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, Download, ExternalLink, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQueryState } from "nuqs";
import { toast } from "sonner";

import { ListSearch } from "@/components/platform/list-search";
import { PageStateEmpty, PageStateError, PageStateLoading } from "@/components/platform/page-state";
import { DEFAULT_PAGE_SIZE_OPTIONS, PaginationControls } from "@/components/platform/pagination-controls";
import { TestcaseWorkspaceNav } from "@/components/platform/testcase-chat-header";
import { TestcaseOverviewStrip } from "@/components/platform/testcase-overview-strip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  exportTestcaseDocumentsExcel,
  getTestcaseBatchDetail,
  getTestcaseDocumentRelations,
  getTestcaseOverview,
  listTestcaseBatches,
  listTestcaseDocuments,
  previewTestcaseDocument,
  downloadTestcaseDocument,
  type TestcaseBatchSummary,
  type TestcaseBatchDetail,
  type TestcaseDocument,
  type TestcaseDocumentRelations,
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

function openPreviewWindowShell(filename?: string) {
  const previewWindow = window.open("", "_blank");
  if (!previewWindow) {
    throw new Error("浏览器阻止了预览窗口，请允许当前站点打开新窗口后重试。");
  }

  previewWindow.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(filename || "document")}</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #eef3fa;
        color: #33465f;
        font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      }
      .preview-loading {
        border-radius: 18px;
        border: 1px solid rgba(118, 145, 178, 0.18);
        background: rgba(255, 255, 255, 0.92);
        padding: 18px 22px;
        box-shadow: 0 18px 40px rgba(67, 93, 126, 0.08);
        font-size: 14px;
        letter-spacing: 0.01em;
      }
    </style>
  </head>
  <body>
    <div class="preview-loading">正在加载预览…</div>
  </body>
</html>`);
  previewWindow.document.close();
  return previewWindow;
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function openBlobPreview(
  blob: Blob,
  options?: { filename?: string; contentType?: string | null; previewWindow?: Window | null },
) {
  const objectUrl = URL.createObjectURL(blob);
  const previewWindow = options?.previewWindow ?? window.open("", "_blank");
  if (!previewWindow) {
    URL.revokeObjectURL(objectUrl);
    throw new Error("浏览器阻止了预览窗口，请允许当前站点打开新窗口后重试。");
  }

  const contentType = options?.contentType || blob.type || "application/octet-stream";
  const filename = options?.filename || "document";

  if (contentType.startsWith("image/")) {
    previewWindow.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(filename)}</title>
    <style>
      body {
        margin: 0;
        background: #dfe7f3;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: "Segoe UI", "PingFang SC", sans-serif;
      }
      img {
        display: block;
        max-width: min(92vw, 1440px);
        max-height: 92vh;
        object-fit: contain;
        border-radius: 18px;
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.16);
        background: rgba(255, 255, 255, 0.82);
      }
    </style>
  </head>
  <body>
    <img src="${objectUrl}" alt="${escapeHtml(filename)}" />
  </body>
</html>`);
    previewWindow.document.close();
  } else {
    previewWindow.location.replace(objectUrl);
  }

  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

function isTextPreviewContentType(contentType: string): boolean {
  return (
    contentType.startsWith("text/") ||
    contentType === "application/json" ||
    contentType === "application/xml" ||
    contentType === "application/javascript"
  );
}

function readBlobAsText(blob: Blob): Promise<string> {
  return blob.text();
}

async function openDocumentPreview(
  blob: Blob,
  options?: { filename?: string; contentType?: string | null; previewWindow?: Window | null },
) {
  const contentType = (options?.contentType || blob.type || "application/octet-stream").toLowerCase();
  if (contentType.startsWith("application/pdf") || contentType.startsWith("image/")) {
    openBlobPreview(blob, options);
    return;
  }

  if (isTextPreviewContentType(contentType)) {
    const text = await readBlobAsText(blob);
    const previewWindow = options?.previewWindow ?? window.open("", "_blank");
    if (!previewWindow) {
      throw new Error("浏览器阻止了预览窗口，请允许当前站点打开新窗口后重试。");
    }
    const filename = options?.filename || "document";
    previewWindow.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(filename)}</title>
    <style>
      body {
        margin: 0;
        padding: 24px;
        background: #eef3fa;
        color: #142033;
        font-family: "SFMono-Regular", "Consolas", "Liberation Mono", monospace;
      }
      pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        line-height: 1.7;
        font-size: 13px;
      }
    </style>
  </head>
  <body>
    <pre>${escapeHtml(text)}</pre>
  </body>
</html>`);
    previewWindow.document.close();
    return;
  }

  throw new Error(`当前类型暂不支持在线预览：${contentType}`);
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

function resolveStoragePath(document: TestcaseDocument | null): string {
  if (!document) {
    return "";
  }
  if (document.storage_path) {
    return document.storage_path;
  }
  const provenance = asRecord(document.provenance);
  const asset = asRecord(provenance.asset);
  return coerceText(asset.storage_path);
}

const PARSE_STATUS_OPTIONS = ["", "parsed", "failed", "unsupported", "unprocessed"];

const INLINE_PREVIEW_CONTENT_TYPES = [
  "application/pdf",
  "application/json",
  "application/xml",
  "application/javascript",
  "text/",
  "image/",
];

function supportsInlinePreview(contentType: string): boolean {
  return INLINE_PREVIEW_CONTENT_TYPES.some((prefix) => contentType.startsWith(prefix));
}

export default function TestcaseDocumentsPage() {
  const router = useRouter();
  const { projectId } = useWorkspaceContext();
  const [batchQuery, setBatchQuery] = useQueryState("batchId", { defaultValue: "" });
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
  const [batchFilter, setBatchFilter] = useState(batchQuery);
  const [parseStatusFilter, setParseStatusFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedItem, setSelectedItem] = useState<TestcaseDocument | null>(null);
  const [relations, setRelations] = useState<TestcaseDocumentRelations | null>(null);
  const [batchDetail, setBatchDetail] = useState<TestcaseBatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [batchDetailLoading, setBatchDetailLoading] = useState(false);
  const [batchDetailError, setBatchDetailError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const selectedBatchLabel = useMemo(
    () => batches.find((item) => item.batch_id === batchFilter)?.batch_id ?? "",
    [batchFilter, batches],
  );
  const storagePath = resolveStoragePath(selectedItem);
  const canAccessDocumentBinary = Boolean(projectId && selectedItem?.id && storagePath);
  const selectedContentType = (selectedItem?.content_type || "").toLowerCase();
  const isPreviewSupported = supportsInlinePreview(selectedContentType);
  const runtimeMeta = useMemo(() => asRecord(relations?.runtime_meta), [relations]);
  const selectedBatchSummary = useMemo(
    () => batchDetail?.batch ?? batches.find((item) => item.batch_id === (selectedItem?.batch_id || "")) ?? null,
    [batchDetail?.batch, batches, selectedItem?.batch_id],
  );
  const batchStatusEntries = useMemo(
    () => Object.entries(selectedBatchSummary?.parse_status_summary ?? {}).sort(([left], [right]) => left.localeCompare(right)),
    [selectedBatchSummary],
  );
  const sameBatchDocuments = useMemo(() => {
    if (!selectedItem?.batch_id) {
      return [];
    }
    return (batchDetail?.documents.items ?? []).filter((item) => item.id !== selectedItem.id);
  }, [batchDetail?.documents.items, selectedItem]);
  const batchPreviewCases = useMemo(() => batchDetail?.test_cases.items ?? [], [batchDetail?.test_cases.items]);

  useEffect(() => {
    const normalized = batchQuery ?? "";
    setBatchFilter((current) => (current === normalized ? current : normalized));
  }, [batchQuery]);

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
      setRelations(null);
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
      setRelations(null);
      return;
    }
    if (!selectedId || !items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  useEffect(() => {
    if (!projectId || !selectedId) {
      setSelectedItem(null);
      setRelations(null);
      setDetailError(null);
      setBatchDetail(null);
      setBatchDetailError(null);
      return;
    }
    let cancelled = false;

    async function loadDetail() {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const payload = await getTestcaseDocumentRelations(projectId, selectedId);
        if (!cancelled) {
          setRelations(payload);
          setSelectedItem(payload.document);
        }
      } catch (err) {
        if (!cancelled) {
          setRelations(null);
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

  useEffect(() => {
    const batchId = selectedItem?.batch_id ?? "";
    if (!projectId || !batchId) {
      setBatchDetail(null);
      setBatchDetailError(null);
      return;
    }
    let cancelled = false;

    async function loadBatchDetail() {
      setBatchDetailLoading(true);
      setBatchDetailError(null);
      try {
        const payload = await getTestcaseBatchDetail(projectId, batchId, {
          document_limit: 100,
          document_offset: 0,
          case_limit: 20,
          case_offset: 0,
        });
        if (!cancelled) {
          setBatchDetail(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setBatchDetail(null);
          setBatchDetailError(err instanceof Error ? err.message : "Failed to load batch detail");
        }
      } finally {
        if (!cancelled) {
          setBatchDetailLoading(false);
        }
      }
    }

    void loadBatchDetail();

    return () => {
      cancelled = true;
    };
  }, [projectId, selectedItem?.batch_id]);

  const handleExport = useCallback(async () => {
    if (!projectId || exporting) {
      return;
    }
    setExporting(true);
    try {
      const download = await exportTestcaseDocumentsExcel(projectId, {
        batch_id: batchFilter || undefined,
        parse_status: parseStatusFilter || undefined,
        query: query || undefined,
      });
      const fallbackName = `testcase-documents-${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}.xlsx`;
      triggerBrowserDownload(download.blob, download.filename || fallbackName);
      toast("导出成功", {
        description: `已导出当前筛选结果，共 ${total} 条文档解析记录。`,
      });
    } catch (err) {
      toast("导出失败", {
        description: err instanceof Error ? err.message : "Failed to export testcase documents",
      });
    } finally {
      setExporting(false);
    }
  }, [batchFilter, exporting, parseStatusFilter, projectId, query, total]);

  const handlePreview = useCallback(async () => {
    if (!projectId || !selectedItem) {
      return;
    }
    if (!isPreviewSupported) {
      toast("当前类型暂不支持在线预览", {
        description: selectedItem.content_type || "unknown",
      });
      return;
    }
    setPreviewing(true);
    let previewWindow: Window | null = null;
    try {
      previewWindow = openPreviewWindowShell(selectedItem.filename);
      const download = await previewTestcaseDocument(projectId, selectedItem.id);
      await openDocumentPreview(download.blob, {
        filename: selectedItem.filename,
        contentType: download.contentType || selectedItem.content_type,
        previewWindow,
      });
    } catch (err) {
      previewWindow?.close();
      toast("预览失败", {
        description: err instanceof Error ? err.message : "Failed to preview testcase document",
      });
    } finally {
      setPreviewing(false);
    }
  }, [isPreviewSupported, projectId, selectedItem]);

  const handleDownload = useCallback(async () => {
    if (!projectId || !selectedItem) {
      return;
    }
    setDownloading(true);
    try {
      const download = await downloadTestcaseDocument(projectId, selectedItem.id);
      const fallbackName = selectedItem.filename || `document-${selectedItem.id}`;
      triggerBrowserDownload(download.blob, download.filename || fallbackName);
    } catch (err) {
      toast("下载失败", {
        description: err instanceof Error ? err.message : "Failed to download testcase document",
      });
    } finally {
      setDownloading(false);
    }
  }, [projectId, selectedItem]);

  const handleCopyDocumentId = useCallback(async () => {
    if (!selectedItem) {
      return;
    }
    try {
      await navigator.clipboard.writeText(selectedItem.id);
      toast("已复制文档 ID", {
        description: selectedItem.id,
      });
    } catch (err) {
      toast("复制失败", {
        description: err instanceof Error ? err.message : "Failed to copy document id",
      });
    }
  }, [selectedItem]);

  const handleCopyBatchId = useCallback(async () => {
    if (!selectedItem?.batch_id) {
      return;
    }
    try {
      await navigator.clipboard.writeText(selectedItem.batch_id);
      toast("已复制批次 ID", {
        description: selectedItem.batch_id,
      });
    } catch (err) {
      toast("复制失败", {
        description: err instanceof Error ? err.message : "Failed to copy batch id",
      });
    }
  }, [selectedItem?.batch_id]);

  const handleViewBatchDocuments = useCallback(() => {
    if (!selectedItem?.batch_id) {
      return;
    }
    setBatchFilter(selectedItem.batch_id);
    void setBatchQuery(selectedItem.batch_id);
    setParseStatusFilter("");
    setQuery("");
    setSearchInput("");
    setOffset(0);
    toast("已切换到当前批次", {
      description: `正在查看批次 ${selectedItem.batch_id} 的全部文档。`,
    });
  }, [selectedItem?.batch_id, setBatchQuery]);

  const handleViewBatchCases = useCallback(() => {
    if (!projectId || !selectedItem?.batch_id) {
      return;
    }
    const params = new URLSearchParams();
    params.set("projectId", projectId);
    params.set("batchId", selectedItem.batch_id);
    router.push(`/workspace/testcase/cases?${params.toString()}`);
  }, [projectId, router, selectedItem?.batch_id]);

  return (
    <section className="p-4 sm:p-6">
      <div className="mb-4">
        <TestcaseWorkspaceNav />
      </div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">文档解析</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            查看已保存到 `interaction-data-service` 的文档解析结果，并追踪 thread / run / testcase 关联。
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => void handleExport()}
          disabled={!projectId || loading || exporting || total <= 0}
        >
          {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
          {exporting ? "导出中..." : "导出文档解析"}
        </Button>
      </div>

      <TestcaseOverviewStrip overview={overview} />

      <div className="mt-4 flex flex-wrap items-center gap-2">
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

      {!projectId ? <PageStateEmpty message="当前没有选中项目，无法读取文档解析结果。" /> : null}
      {projectId && loading ? <PageStateLoading message="Loading testcase documents..." /> : null}
      {projectId && error ? <PageStateError message={error} /> : null}

      {projectId && !loading && !error && items.length === 0 ? (
        <PageStateEmpty
          message={
            selectedBatchLabel
              ? `批次 ${selectedBatchLabel} 暂无文档解析结果。`
              : "当前项目下还没有保存过文档解析结果。"
          }
        />
      ) : null}

      {projectId && !loading && !error && items.length > 0 ? (
        <>
          <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(380px,1fr)]">
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
                              <div className="mt-1 text-xs text-muted-foreground">{item.content_type}</div>
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

            <Card className="min-w-0 gap-4 py-4">
              <CardHeader className="px-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <CardTitle className="text-base">解析详情</CardTitle>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void handleCopyDocumentId()}
                      disabled={!selectedItem}
                    >
                      <Copy className="size-4" />
                      复制文档 ID
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void handlePreview()}
                      disabled={!canAccessDocumentBinary || !isPreviewSupported || previewing}
                    >
                      {previewing ? <Loader2 className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
                      在线预览
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void handleDownload()}
                      disabled={!canAccessDocumentBinary || downloading}
                    >
                      {downloading ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                      下载原始文件
                    </Button>
                  </div>
                </div>
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
                    <dl className="min-w-0 grid gap-3 text-sm">
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">解析状态</dt>
                        <dd className="mt-1">{selectedItem.parse_status}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">批次</dt>
                        <dd className="mt-1 break-all">{selectedItem.batch_id || "-"}</dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">原始文件路径</dt>
                        <dd className="mt-1 break-all text-muted-foreground">
                          {storagePath || "当前记录未保存原始文件路径，仅保留了解析结果。"}
                        </dd>
                      </div>
                      {!storagePath ? (
                        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-700">
                          当前记录没有回填 `storage_path`，说明原始文件资产尚未落库，当前无法在线预览或下载原始文件。
                        </div>
                      ) : null}
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">预览能力</dt>
                        <dd className="mt-1 text-sm text-muted-foreground">
                          {isPreviewSupported
                            ? `当前支持在线预览，类型为 ${selectedItem.content_type || "unknown"}。`
                            : `当前仅支持下载，暂不支持在线预览 ${selectedItem.content_type || "unknown"}。`}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">运行态追踪</dt>
                        <dd className="mt-2 rounded-lg bg-muted/30 p-3 text-xs leading-6 text-muted-foreground">
                          <div>thread_id: {coerceText(runtimeMeta.thread_id) || "-"}</div>
                          <div>run_id: {coerceText(runtimeMeta.run_id) || "-"}</div>
                          <div>agent_key: {coerceText(runtimeMeta.agent_key) || "-"}</div>
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Batch Context</dt>
                        <dd className="mt-2 rounded-lg border border-border bg-muted/20 p-3">
                          {selectedItem.batch_id ? (
                            <div className="space-y-4">
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="space-y-1">
                                  <div className="font-medium text-foreground break-all">{selectedItem.batch_id}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {selectedBatchSummary
                                      ? `documents=${selectedBatchSummary.documents_count} / test_cases=${selectedBatchSummary.test_cases_count}`
                                      : "当前批次未命中汇总信息，可能是筛选条件限制。"}
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  <Button type="button" variant="outline" size="sm" onClick={() => void handleCopyBatchId()}>
                                    <Copy className="size-4" />
                                    复制 batch_id
                                  </Button>
                                  <Button type="button" variant="outline" size="sm" onClick={handleViewBatchDocuments}>
                                    查看同批次全部文档
                                  </Button>
                                  <Button type="button" variant="outline" size="sm" onClick={handleViewBatchCases}>
                                    查看同批次全部用例
                                  </Button>
                                </div>
                              </div>

                              {batchDetailLoading ? (
                                <div className="text-xs text-muted-foreground">Loading batch detail...</div>
                              ) : null}
                              {batchDetailError ? (
                                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                                  {batchDetailError}
                                </div>
                              ) : null}

                              {selectedBatchSummary ? (
                                <div className="grid gap-3 sm:grid-cols-2">
                                  <div className="rounded-md border border-border bg-background px-3 py-2">
                                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">documents_count</div>
                                    <div className="mt-1 text-sm font-medium">{selectedBatchSummary.documents_count}</div>
                                  </div>
                                  <div className="rounded-md border border-border bg-background px-3 py-2">
                                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">test_cases_count</div>
                                    <div className="mt-1 text-sm font-medium">{selectedBatchSummary.test_cases_count}</div>
                                  </div>
                                  <div className="rounded-md border border-border bg-background px-3 py-2 sm:col-span-2">
                                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">latest_created_at</div>
                                    <div className="mt-1 text-sm">{formatDateTime(selectedBatchSummary.latest_created_at)}</div>
                                  </div>
                                  <div className="rounded-md border border-border bg-background px-3 py-2 sm:col-span-2">
                                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">parse_status_summary</div>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {batchStatusEntries.length > 0 ? (
                                        batchStatusEntries.map(([status, count]) => (
                                          <span key={status} className="rounded-full border border-border px-2 py-1 text-xs text-muted-foreground">
                                            {status}: {count}
                                          </span>
                                        ))
                                      ) : (
                                        <span className="text-xs text-muted-foreground">当前批次暂无状态汇总。</span>
                                      )}
                                    </div>
                                  </div>
                                  <div className="rounded-md border border-border bg-background px-3 py-2 sm:col-span-2">
                                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">batch_test_cases_preview</div>
                                    <div className="mt-2 space-y-2">
                                      {batchPreviewCases.length > 0 ? (
                                        batchPreviewCases.map((item) => (
                                          <div key={item.id} className="rounded-md border border-border/80 bg-muted/20 px-3 py-2">
                                            <div className="font-medium text-foreground">{item.title}</div>
                                            <div className="mt-1 text-xs text-muted-foreground">
                                              {item.case_id || item.id} / {item.status} / {formatDateTime(item.updated_at)}
                                            </div>
                                          </div>
                                        ))
                                      ) : (
                                        <div className="text-xs text-muted-foreground">当前批次暂无 testcase 预览数据。</div>
                                      )}
                                      {batchDetail && batchDetail.test_cases.total > batchPreviewCases.length ? (
                                        <div className="text-xs text-muted-foreground">
                                          当前仅展示前 {batchPreviewCases.length} 条，用“查看同批次全部用例”进入完整列表。
                                        </div>
                                      ) : null}
                                    </div>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : (
                            <div className="text-xs leading-6 text-muted-foreground">
                              当前 document 没有关联 batch_id，暂时只能查看单 document 详情。
                            </div>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">本文档关联用例</dt>
                        <dd className="mt-2 rounded-lg bg-muted/20 p-3 text-xs leading-6">
                          <div className="mb-2 text-muted-foreground">共 {relations?.related_cases_count ?? 0} 条关联用例</div>
                          {relations && relations.related_cases.length > 0 ? (
                            <div className="space-y-2">
                              {relations.related_cases.map((item) => (
                                <div key={item.id} className="rounded-md border border-border bg-background px-3 py-2">
                                  <div className="font-medium text-foreground">{item.title}</div>
                                  <div className="text-muted-foreground mt-1">{item.case_id || item.id}</div>
                                  <div className="text-muted-foreground">{item.status} / {item.batch_id || "-"}</div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-muted-foreground">当前 document 尚未关联到正式测试用例。</div>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">同批次其他文档</dt>
                        <dd className="mt-2 rounded-lg bg-muted/20 p-3 text-xs leading-6">
                          {selectedItem.batch_id ? (
                            <>
                              <div className="mb-2 text-muted-foreground">
                                当前批次接口返回 {sameBatchDocuments.length} 条其他文档；
                                {selectedBatchSummary ? `批次总量 ${selectedBatchSummary.documents_count} 条。` : "批次汇总暂不可用。"}
                              </div>
                              {sameBatchDocuments.length > 0 ? (
                                <div className="space-y-2">
                                  {sameBatchDocuments.map((item) => (
                                    <button
                                      key={item.id}
                                      type="button"
                                      className="block w-full rounded-md border border-border bg-background px-3 py-2 text-left transition-colors hover:bg-muted/20"
                                      onClick={() => setSelectedId(item.id)}
                                    >
                                      <div className="font-medium text-foreground">{item.filename}</div>
                                      <div className="mt-1 text-muted-foreground">{item.parse_status} / {formatDateTime(item.created_at)}</div>
                                    </button>
                                  ))}
                                </div>
                              ) : (
                                <div className="text-muted-foreground">
                                  当前批次没有其他文档，或当前接口返回结果中仅包含当前 document。
                                </div>
                              )}
                              {batchDetail && batchDetail.documents.total > sameBatchDocuments.length + 1 ? (
                                <div className="mt-2 text-muted-foreground">
                                  当前仅展示前 {batchDetail.documents.items.length} 条批次文档，可点击“查看同批次全部文档”进入完整筛选列表。
                                </div>
                              ) : null}
                            </>
                          ) : (
                            <div className="text-muted-foreground">当前 document 没有关联 batch_id。</div>
                          )}
                        </dd>
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
                            <pre className="max-h-[240px] max-w-full overflow-auto rounded-lg bg-muted/40 p-3 text-xs leading-6 whitespace-pre-wrap break-all">
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
                          <pre className="max-h-[220px] max-w-full overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-3 text-xs leading-6">
                            {stringifyJson(selectedItem.structured_data)}
                          </pre>
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">provenance</dt>
                        <dd className="mt-2">
                          <pre className="max-h-[200px] max-w-full overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-3 text-xs leading-6">
                            {stringifyJson(selectedItem.provenance)}
                          </pre>
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs uppercase tracking-[0.18em] text-muted-foreground">error</dt>
                        <dd className="mt-2">
                          <pre className="max-h-[140px] max-w-full overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted/40 p-3 text-xs leading-6">
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
