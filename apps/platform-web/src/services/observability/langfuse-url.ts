import { env } from "@/config/env";

export interface BuildLangfuseUrlOptions {
  projectId?: string;
  baseUrl?: string;
  template?: string;
}

/**
 * 组装 Langfuse Trace 直达 URL
 * 支持三级自适应解析：
 * 1. 显式模板替换 (VITE_LANGFUSE_TRACE_URL_TEMPLATE 或 options.template)；
 * 2. 项目级搜索过滤直达 (VITE_LANGFUSE_PROJECT_ID 或 options.projectId)，精准适配多租户 SaaS，杜绝 404；
 * 3. 兜底默认回退 (base/trace/{traceId})。
 */
export function buildLangfuseTraceUrl(
  traceId: string,
  options: BuildLangfuseUrlOptions = {},
): string {
  const id = traceId.trim();
  if (!id) return "";

  const template = (
    options.template ||
    env.langfuseTraceUrlTemplate ||
    ""
  ).trim();
  if (template) {
    return template.split("{traceId}").join(encodeURIComponent(id));
  }

  const base = (
    options.baseUrl ||
    env.langfuseBaseUrl ||
    "https://jp.cloud.langfuse.com"
  ).replace(/\/+$/, "");
  const projectId = (options.projectId || env.langfuseProjectId || "").trim();

  if (projectId) {
    const params = new URLSearchParams();
    params.set("filter", "isRootObservation;boolean;;=;true");
    params.append("searchType", "id");
    params.append("searchType", "content");
    params.set("traceTab", "attributes");
    params.set("search", id);
    return `${base}/project/${encodeURIComponent(projectId)}/traces?${params.toString()}`;
  }

  return `${base}/trace/${encodeURIComponent(id)}`;
}
