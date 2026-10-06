import { platformHttpClient } from "@/services/http/client";
import type {
  SuggestionsConfigResponse,
  SuggestionsPayload,
  SuggestionsResponse,
} from "./types";

const configCache = new Map<string, Promise<SuggestionsConfigResponse>>();

export function _resetSuggestionsConfigCache(): void {
  configCache.clear();
}

export async function loadSuggestionsConfig(
  projectId: string,
  signal?: AbortSignal,
): Promise<SuggestionsConfigResponse> {
  const cached = configCache.get(projectId);
  if (cached) {
    return cached;
  }

  const promise = (async () => {
    try {
      const response = await platformHttpClient.get<SuggestionsConfigResponse>(
        "/api/langgraph/suggestions/config",
        {
          headers: { "x-project-id": projectId },
          signal,
        },
      );
      return response.data;
    } catch {
      // 容错降级：配置加载失败时安全默认关闭，避免阻断界面
      return { enabled: false, max_suggestions: 3 };
    }
  })();

  configCache.set(projectId, promise);
  return promise;
}

export async function generateThreadSuggestions(
  projectId: string,
  threadId: string,
  payload: SuggestionsPayload,
  signal?: AbortSignal,
): Promise<string[]> {
  try {
    const response = await platformHttpClient.post<SuggestionsResponse>(
      `/api/langgraph/threads/${threadId}/suggestions`,
      payload,
      {
        headers: { "x-project-id": projectId },
        signal,
      },
    );
    return Array.isArray(response.data?.suggestions)
      ? response.data.suggestions
          .map((item) => (typeof item === "string" ? item.trim() : ""))
          .filter((item) => item.length > 0)
      : [];
  } catch {
    // best-effort 契约：任何异常降级返回空数组，静默收起建议区
    return [];
  }
}
