import { platformHttpClient } from "@/services/http/client";

export interface RuntimeFileRef {
  version: 1;
  path: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
}

export const ALLOWED_DOCUMENT_MIMES = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "application/json",
  "text/csv",
  "application/zip",
  "application/x-zip-compressed",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "text/html",
  "text/css",
  "text/javascript",
] as const;

export const ALLOWED_DOCUMENT_EXTENSIONS = [
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
  ".json",
  ".csv",
  ".zip",
  ".xlsx",
  ".xls",
  ".html",
  ".htm",
  ".css",
  ".js",
] as const;

export function isValidFileRef(val: unknown): val is RuntimeFileRef {
  if (!val || typeof val !== "object" || Array.isArray(val)) {
    return false;
  }
  const obj = val as Record<string, unknown>;
  if (obj.version !== 1) {
    return false;
  }
  if (typeof obj.path !== "string" || !obj.path) {
    return false;
  }
  if (
    !obj.path.startsWith("/workspace/uploads/") &&
    !obj.path.startsWith("/workspace/outputs/")
  ) {
    return false;
  }
  if (typeof obj.mime_type !== "string" || !obj.mime_type) {
    return false;
  }
  if (typeof obj.size_bytes !== "number" || obj.size_bytes <= 0) {
    return false;
  }
  if (
    typeof obj.sha256 !== "string" ||
    obj.sha256.length !== 64 ||
    !/^[0-9a-f]{64}$/.test(obj.sha256)
  ) {
    return false;
  }
  return true;
}

export async function calculateFileSha256(file: Blob): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const array = Array.from(new Uint8Array(digest));
  return array.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function uploadThreadFile(
  projectId: string,
  threadId: string,
  sha256: string,
  file: File,
): Promise<RuntimeFileRef> {
  const mimeType = file.type || "application/octet-stream";
  const { data } = await platformHttpClient.put<RuntimeFileRef>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/files/uploads/${encodeURIComponent(sha256)}`,
    file,
    {
      params: {
        file_name: file.name,
      },
      headers: {
        "x-project-id": projectId,
        "Content-Type": mimeType,
      },
    },
  );
  if (!isValidFileRef(data)) {
    throw new Error("服务端返回的文档引用格式不合法");
  }
  return data;
}

export async function getThreadFileBlob(
  projectId: string,
  threadId: string,
  path: string,
): Promise<Blob> {
  const response = await platformHttpClient.get(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/files/content`,
    {
      params: { path },
      headers: {
        "x-project-id": projectId,
      },
      responseType: "blob",
    },
  );
  return response.data;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function parseCsvToHtmlTable(csvText: string): string {
  const lines = csvText.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return '<p style="padding: 20px; color: var(--text-sub);">文件内容为空</p>';

  const parseLine = (line: string): string[] => {
    const values: string[] = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === "," && !inQuotes) {
        values.push(current);
        current = "";
      } else {
        current += char;
      }
    }
    values.push(current);
    return values;
  };

  const rows = lines.map(parseLine);
  const header = rows[0] || [];
  const dataRows = rows.slice(1);

  let html = '<div class="table-container"><table><thead><tr>';
  html += '<th class="row-num">#</th>';
  for (const h of header) {
    html += `<th>${escapeHtml(h.trim())}</th>`;
  }
  html += "</tr></thead><tbody>";

  dataRows.forEach((r, idx) => {
    html += `<tr><td class="row-num">${idx + 1}</td>`;
    for (let c = 0; c < header.length; c++) {
      html += `<td>${escapeHtml((r[c] ?? "").trim())}</td>`;
    }
    html += "</tr>";
  });

  html += "</tbody></table></div>";
  return html;
}

function buildPreviewHtml(fileName: string, type: "csv" | "markdown" | "text" | "json", textContent: string): string {
  const safeName = escapeHtml(fileName);
  let bodyContent = "";
  if (type === "csv") {
    bodyContent = `
      <div class="content-header">
        <span class="badge badge-csv">CSV 表格</span>
        <span class="file-name">${safeName}</span>
      </div>
      ${parseCsvToHtmlTable(textContent)}
    `;
  } else if (type === "markdown") {
    bodyContent = `
      <div class="content-header">
        <span class="badge badge-md">Markdown</span>
        <span class="file-name">${safeName}</span>
      </div>
      <div class="code-container"><pre><code>${escapeHtml(textContent)}</code></pre></div>
    `;
  } else if (type === "json") {
    let formatted = textContent;
    try {
      formatted = JSON.stringify(JSON.parse(textContent), null, 2);
    } catch {
      // 保持原始未格式化内容
    }
    bodyContent = `
      <div class="content-header">
        <span class="badge badge-json">JSON</span>
        <span class="file-name">${safeName}</span>
      </div>
      <div class="code-container"><pre><code>${escapeHtml(formatted)}</code></pre></div>
    `;
  } else {
    bodyContent = `
      <div class="content-header">
        <span class="badge badge-txt">纯文本</span>
        <span class="file-name">${safeName}</span>
      </div>
      <div class="code-container"><pre><code>${escapeHtml(textContent)}</code></pre></div>
    `;
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${safeName}</title>
  <style>
    :root {
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #1e293b;
      --text-sub: #64748b;
      --border: #e2e8f0;
      --header-bg: #f1f5f9;
      --code-bg: #f8fafc;
      --th-bg: #f1f5f9;
      --stripe: #f8fafc;
      --hover: #f1f5f9;
      --badge-bg: #e2e8f0;
      --badge-text: #475569;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0f172a;
        --card-bg: #1e293b;
        --text: #f1f5f9;
        --text-sub: #94a3b8;
        --border: #334155;
        --header-bg: #0f172a;
        --code-bg: #0f172a;
        --th-bg: #0f172a;
        --stripe: rgba(30, 41, 59, 0.5);
        --hover: #334155;
        --badge-bg: #334155;
        --badge-text: #cbd5e1;
      }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }
    .wrapper {
      max-width: 1200px;
      margin: 0 auto;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .content-header {
      padding: 14px 20px;
      border-bottom: 1px solid var(--border);
      background: var(--header-bg);
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 6px;
      background: var(--badge-bg);
      color: var(--badge-text);
      letter-spacing: 0.02em;
    }
    .badge-csv { background: #dcfce7; color: #15803d; }
    .badge-md { background: #dbeafe; color: #1d4ed8; }
    .badge-json { background: #fef3c7; color: #b45309; }
    .badge-txt { background: #f1f5f9; color: #475569; }
    @media (prefers-color-scheme: dark) {
      .badge-csv { background: rgba(22, 101, 52, 0.4); color: #86efac; }
      .badge-md { background: rgba(30, 58, 138, 0.4); color: #93c5fd; }
      .badge-json { background: rgba(120, 53, 15, 0.4); color: #fcd34d; }
      .badge-txt { background: rgba(51, 65, 85, 0.5); color: #cbd5e1; }
    }
    .file-name {
      font-weight: 600;
      font-size: 14px;
      word-break: break-all;
    }
    .code-container {
      padding: 20px;
      overflow-x: auto;
      background: var(--code-bg);
    }
    pre {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 13px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .table-container {
      overflow: auto;
      max-height: 85vh;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      text-align: left;
    }
    th, td {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
      border-right: 1px solid var(--border);
      white-space: nowrap;
    }
    th {
      background: var(--th-bg);
      font-weight: 600;
      color: var(--text-sub);
      position: sticky;
      top: 0;
      z-index: 1;
    }
    .row-num {
      width: 48px;
      text-align: center;
      color: var(--text-sub);
      background: var(--th-bg);
      font-size: 11px;
      user-select: none;
    }
    tr:nth-child(even) td {
      background: var(--stripe);
    }
    tr:hover td {
      background: var(--hover);
    }
  </style>
</head>
<body>
  <div class="wrapper">
    ${bodyContent}
  </div>
</body>
</html>`;
}

async function readBlobAsText(blob: Blob): Promise<string> {
  if (typeof blob.text === "function") {
    return await blob.text();
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob, "utf-8");
  });
}

export async function previewThreadFileInNewTab(
  projectId: string,
  threadId: string,
  path: string,
  fileName?: string,
): Promise<void> {
  const name = fileName || path.split("/").pop() || "document";
  const lower = name.toLowerCase();

  // ZIP/PPTX/Excel 等二进制文件禁止文本预览，直接走安全原字节下载
  if (
    lower.endsWith(".zip") ||
    lower.endsWith(".pptx") ||
    lower.endsWith(".xlsx") ||
    lower.endsWith(".xls") ||
    lower.endsWith(".bin")
  ) {
    await downloadThreadFile(projectId, threadId, path, fileName);
    return;
  }

  const blob = await getThreadFileBlob(projectId, threadId, path);
  const mime = (blob.type || "").toLowerCase();

  let targetBlob: Blob;
  if (lower.endsWith(".pdf") || mime.includes("pdf")) {
    targetBlob = blob.type === "application/pdf" ? blob : new Blob([blob], { type: "application/pdf" });
  } else {
    // 文本类文档：使用 readBlobAsText 原生 UTF-8 解码，杜绝字符集乱码，并渲染为带样式的 HTML 视窗（避免 CSV 被浏览器强制下载）
    const textContent = await readBlobAsText(blob);
    let type: "csv" | "markdown" | "text" | "json" = "text";
    if (lower.endsWith(".csv") || mime.includes("csv")) type = "csv";
    else if (lower.endsWith(".md") || lower.endsWith(".markdown") || mime.includes("markdown")) type = "markdown";
    else if (lower.endsWith(".json") || mime.includes("json")) type = "json";

    const html = buildPreviewHtml(name, type, textContent);
    targetBlob = new Blob([html], { type: "text/html;charset=utf-8" });
  }

  const objectUrl = URL.createObjectURL(targetBlob);
  const opened = window.open(objectUrl, "_blank");
  if (!opened) {
    // 降级处理：若弹窗被浏览器拦截则创建临时链接模拟点击
    const a = document.createElement("a");
    a.href = objectUrl;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
  // 延迟回收 Object URL
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
}

export async function downloadThreadFile(
  projectId: string,
  threadId: string,
  path: string,
  fileName?: string,
): Promise<void> {
  const blob = await getThreadFileBlob(projectId, threadId, path);
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = fileName || path.split("/").pop() || "download";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
}
