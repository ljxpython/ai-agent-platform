import { Client } from "@langchain/langgraph-sdk";
import {
  createLanggraphAuthorizedFetch,
  getLanggraphApiUrl,
} from "@/services/langgraph/client";
import { platformHttpClient } from "@/services/http/client";
import type { AssistantCapabilities, BootstrapConfig } from "../types";

/**
 * 初始化平台助手：获取绑定的 project_id、model_id 等核心配置
 * - 若指定 targetProjectId，则携带该项目头；
 * - 若未指定，则不带，后端幂等创建或复用仅本人加入的“个人助手”项目。
 */
export async function bootstrapAssistant(
  targetProjectId?: string,
): Promise<BootstrapConfig> {
  const headers: Record<string, string> = {};
  const normalizedId = targetProjectId?.trim();
  if (normalizedId) {
    headers["x-project-id"] = normalizedId;
  }

  const res = await platformHttpClient.post<BootstrapConfig>(
    "/api/platform-assistant/bootstrap",
    undefined,
    { headers },
  );

  return res.data;
}

/**
 * 获取当前项目下的平台助手能力声明
 */
export async function getAssistantCapabilities(
  projectId: string,
): Promise<AssistantCapabilities> {
  const res = await platformHttpClient.get<AssistantCapabilities>(
    "/api/platform-assistant/capabilities",
    {
      headers: {
        "x-project-id": projectId.trim(),
      },
    },
  );

  return res.data;
}

/**
 * 创建专属的 Scoped Langgraph Client
 * 关键架构规则：其默认请求头中的 x-project-id 严格锁定为 bootstrap 返回的 project_id，
 * 绝不读取全局 useProjectStore 动态变化的值，彻底隔离串台与权限误判风险。
 */
export function createAssistantScopedClient(projectId: string): Client {
  const normalizedProjectId = projectId.trim();
  if (!normalizedProjectId) {
    throw new Error("初始化平台助手 Client 必须提供有效的 project_id");
  }

  return new Client({
    apiUrl: getLanggraphApiUrl(),
    callerOptions: {
      fetch: createLanggraphAuthorizedFetch(),
      maxRetries: 0,
    },
    defaultHeaders: {
      "x-project-id": normalizedProjectId,
    },
  });
}
