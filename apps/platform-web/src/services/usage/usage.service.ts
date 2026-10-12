import { platformHttpClient } from "@/services/http/client";
import {
  UsageDashboardV1Schema,
  UsageRunPageV1Schema,
  type UsageDashboardV1,
  type UsageRunPageV1,
  type DashboardQueryParams,
  type RunsQueryParams,
} from "@/modules/usage/types";
import { extractPlatformHttpError } from "@/utils/http-error";

export interface RequestOptions {
  signal?: AbortSignal;
}

/**
 * 自定义原生重复键参数序列化器
 * 确保类似 project_ids 生成 project_ids=1&project_ids=2，绝不产生中括号 project_ids[]=1
 */
function serializeParams(params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") {
          searchParams.append(key, String(item).trim());
        }
      }
    } else {
      searchParams.append(key, String(value).trim());
    }
  }
  return searchParams.toString();
}

/**
 * 过滤平台看板白名单参数
 */
function buildPlatformDashboardParams(
  raw: DashboardQueryParams,
): Record<string, unknown> {
  const params: Record<string, unknown> = {
    from: raw.from,
    to: raw.to,
  };
  if (raw.timezone) params.timezone = raw.timezone;
  if (raw.granularity) params.granularity = raw.granularity;
  if (raw.project_ids && raw.project_ids.length > 0) {
    params.project_ids = raw.project_ids;
  }
  if (raw.model_id) params.model_id = raw.model_id;
  if (raw.model_mapping) params.model_mapping = raw.model_mapping;
  if (raw.agent_id) params.agent_id = raw.agent_id;
  if (raw.purpose) params.purpose = raw.purpose;
  if (raw.scope) params.scope = raw.scope;
  if (raw.group_by) params.group_by = raw.group_by;
  if (raw.rank_by) params.rank_by = raw.rank_by;
  if (typeof raw.top_n === "number" && raw.top_n > 0) params.top_n = raw.top_n;
  return params;
}

/**
 * 过滤单项目看板白名单参数（严禁携带 project_ids）
 */
function buildProjectDashboardParams(
  raw: DashboardQueryParams,
): Record<string, unknown> {
  const params: Record<string, unknown> = {
    from: raw.from,
    to: raw.to,
  };
  if (raw.timezone) params.timezone = raw.timezone;
  if (raw.granularity) params.granularity = raw.granularity;
  if (raw.model_id) params.model_id = raw.model_id;
  if (raw.model_mapping) params.model_mapping = raw.model_mapping;
  if (raw.agent_id) params.agent_id = raw.agent_id;
  if (raw.purpose) params.purpose = raw.purpose;
  if (raw.scope) params.scope = raw.scope;
  if (raw.group_by) params.group_by = raw.group_by;
  if (raw.rank_by) params.rank_by = raw.rank_by;
  if (typeof raw.top_n === "number" && raw.top_n > 0) params.top_n = raw.top_n;
  return params;
}

/**
 * 过滤 Runs 运行明细白名单参数（绝不传递看板专有参数）
 */
function buildRunsParams(raw: RunsQueryParams): Record<string, unknown> {
  const params: Record<string, unknown> = {
    from: raw.from,
    to: raw.to,
  };
  if (raw.model_id) params.model_id = raw.model_id;
  if (raw.model_mapping) params.model_mapping = raw.model_mapping;
  if (raw.agent_id) params.agent_id = raw.agent_id;
  if (raw.purpose) params.purpose = raw.purpose;
  if (raw.scope) params.scope = raw.scope;
  if (typeof raw.limit === "number" && raw.limit > 0) params.limit = raw.limit;
  if (raw.cursor && raw.cursor.trim()) params.cursor = raw.cursor.trim();
  return params;
}

/**
 * 查询平台全局 Token 用量看板
 * 接口：GET /api/usage/dashboard
 */
export async function getPlatformUsageDashboard(
  queryParams: DashboardQueryParams,
  options: RequestOptions = {},
): Promise<UsageDashboardV1> {
  const params = buildPlatformDashboardParams(queryParams);
  try {
    const response = await platformHttpClient.get<unknown>(
      "/api/usage/dashboard",
      {
        params,
        paramsSerializer: serializeParams,
        signal: options.signal,
      },
    );
    const parsed = UsageDashboardV1Schema.safeParse(response.data);
    if (!parsed.success) {
      throw Object.assign(
        new Error(`平台用量看板响应结构校验失败: ${parsed.error.message}`),
        { code: "invalid_usage_dto" },
      );
    }
    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) throw error;
    const fields = extractPlatformHttpError(error, "获取平台用量看板失败");
    const enhancedError = new Error(fields.message || "获取平台用量看板失败");
    Object.assign(enhancedError, fields);
    throw enhancedError;
  }
}

/**
 * 查询单项目 Token 用量看板
 * 接口：GET /api/projects/{projectId}/usage/dashboard
 */
export async function getProjectUsageDashboard(
  projectId: string,
  queryParams: DashboardQueryParams,
  options: RequestOptions = {},
): Promise<UsageDashboardV1> {
  const trimmedProjectId = (projectId || "").trim();
  if (!trimmedProjectId) {
    throw new Error("projectId 不能为空");
  }
  const params = buildProjectDashboardParams(queryParams);
  try {
    const url = `/api/projects/${encodeURIComponent(trimmedProjectId)}/usage/dashboard`;
    const response = await platformHttpClient.get<unknown>(url, {
      params,
      paramsSerializer: serializeParams,
      signal: options.signal,
    });
    const parsed = UsageDashboardV1Schema.safeParse(response.data);
    if (!parsed.success) {
      throw Object.assign(
        new Error(`项目用量看板响应结构校验失败: ${parsed.error.message}`),
        { code: "invalid_usage_dto" },
      );
    }
    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) throw error;
    const fields = extractPlatformHttpError(error, "获取项目用量看板失败");
    const enhancedError = new Error(fields.message || "获取项目用量看板失败");
    Object.assign(enhancedError, fields);
    throw enhancedError;
  }
}

/**
 * 查询单项目的可访问运行明细列表（支持 keyset 游标分页）
 * 接口：GET /api/projects/{projectId}/usage/runs
 */
export async function getProjectUsageRuns(
  projectId: string,
  queryParams: RunsQueryParams,
  options: RequestOptions = {},
): Promise<UsageRunPageV1> {
  const trimmedProjectId = (projectId || "").trim();
  if (!trimmedProjectId) {
    throw new Error("projectId 不能为空");
  }
  const params = buildRunsParams(queryParams);
  try {
    const url = `/api/projects/${encodeURIComponent(trimmedProjectId)}/usage/runs`;
    const response = await platformHttpClient.get<unknown>(url, {
      params,
      paramsSerializer: serializeParams,
      signal: options.signal,
    });
    const parsed = UsageRunPageV1Schema.safeParse(response.data);
    if (!parsed.success) {
      throw Object.assign(
        new Error(`运行明细分页响应结构校验失败: ${parsed.error.message}`),
        { code: "invalid_usage_dto" },
      );
    }
    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) throw error;
    const fields = extractPlatformHttpError(error, "获取运行明细分页失败");
    const enhancedError = new Error(fields.message || "获取运行明细分页失败");
    Object.assign(enhancedError, fields);
    throw enhancedError;
  }
}
