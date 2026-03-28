import type { Thread } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  createContext,
  useCallback,
  useContext,
  useState,
} from "react";
import { getApiKey } from "@/lib/api-key";
import { logClient } from "@/lib/client-logger";
import { getConfiguredPlatformApiUrl } from "@/lib/platform-api-url";
import { isJwtToken } from "@/lib/token";
import { createClient } from "./client";
import { useWorkspaceContext } from "./WorkspaceContext";

function isDirectRuntimeUrl(apiUrl: string): boolean {
  try {
    const parsed = new URL(apiUrl);
    return (
      ["localhost", "127.0.0.1"].includes(parsed.hostname) &&
      ["8123", "8124"].includes(parsed.port)
    );
  } catch {
    return apiUrl.includes(":8123") || apiUrl.includes(":8124");
  }
}

function normalizeApiUrl(apiUrl: string, fallbackApiUrl?: string): string {
  if (isDirectRuntimeUrl(apiUrl)) {
    return fallbackApiUrl || getConfiguredPlatformApiUrl();
  }
  return apiUrl;
}

function appendLangGraphApiPrefix(apiUrl: string): string {
  if (!apiUrl) {
    return apiUrl;
  }

  const normalizedBase = apiUrl.replace(/\/+$/, "");
  if (normalizedBase.endsWith("/api/langgraph")) {
    return normalizedBase;
  }

  return `${normalizedBase}/api/langgraph`;
}

interface ThreadContextType {
  getThreads: () => Promise<Thread[]>;
  updateThreadState: (
    threadId: string,
    values: Record<string, unknown>,
  ) => Promise<void>;
  threads: Thread[];
  setThreads: Dispatch<SetStateAction<Thread[]>>;
  threadsLoading: boolean;
  setThreadsLoading: Dispatch<SetStateAction<boolean>>;
}

const ThreadContext = createContext<ThreadContextType | undefined>(undefined);

function getThreadSearchMetadata(
  targetType: string,
  targetId: string,
): { graph_id: string } | { assistant_id: string } {
  if (targetType === "graph") {
    return { graph_id: targetId };
  }

  return { assistant_id: targetId };
}

export function ThreadProvider({
  children,
  initialApiUrl,
  initialAssistantId,
  initialGraphId,
  initialTargetType,
}: {
  children: ReactNode;
  initialApiUrl?: string;
  initialAssistantId?: string;
  initialGraphId?: string;
  initialTargetType?: "assistant" | "graph";
}) {
  const { projectId } = useWorkspaceContext();
  const autoTokenEnabled = process.env.NEXT_PUBLIC_AUTO_ACCESS_TOKEN === "true";
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined = process.env.NEXT_PUBLIC_ASSISTANT_ID;

  const [apiUrl] = useQueryState("apiUrl", {
    defaultValue: initialApiUrl || "",
  });
  const [assistantId] = useQueryState("assistantId", {
    defaultValue: initialAssistantId || "",
  });
  const [graphId] = useQueryState("graphId", {
    defaultValue: initialGraphId || "",
  });
  const [targetType] = useQueryState("targetType", {
    defaultValue: initialTargetType || "assistant",
  });
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);

  const buildClient = useCallback(() => {
    const finalApiUrl = appendLangGraphApiPrefix(
      normalizeApiUrl(apiUrl || envApiUrl || "", envApiUrl),
    );
    if (!finalApiUrl) {
      return null;
    }

    const rawApiKey = getApiKey();
    const clientApiKey =
      rawApiKey && (!autoTokenEnabled || isJwtToken(rawApiKey))
        ? rawApiKey
        : undefined;

    return createClient(finalApiUrl, clientApiKey, {
      ...(projectId ? { "x-project-id": projectId } : {}),
    });
  }, [apiUrl, envApiUrl, projectId, autoTokenEnabled]);

  const getThreads = useCallback(async (): Promise<Thread[]> => {
    const finalApiUrl = appendLangGraphApiPrefix(
      normalizeApiUrl(apiUrl || envApiUrl || "", envApiUrl),
    );
    const finalTargetId =
      (targetType === "graph" ? graphId || assistantId : assistantId || envAssistantId) || "";
    if (!finalApiUrl || !finalTargetId) return [];
    const client = buildClient();
    if (!client) {
      return [];
    }

    try {
        const threads = await client.threads.search({
          metadata: {
            ...getThreadSearchMetadata(targetType || "assistant", finalTargetId),
          },
        limit: 100,
        select: ["thread_id", "created_at", "updated_at", "metadata", "status"],
      });

      logClient({
        level: "debug",
        event: "thread_list_loaded",
        message: "Loaded threads list",
        context: {
          assistantId: finalTargetId,
          count: threads.length,
        },
      });

      return threads;
    } catch (error) {
      logClient({
        level: "error",
        event: "thread_list_load_error",
        message: "Failed to load threads list",
        context: {
          assistantId: finalTargetId,
          apiUrl: finalApiUrl,
          error: String(error),
        },
      });

      throw error;
    }
  }, [
    apiUrl,
    assistantId,
    graphId,
    envApiUrl,
    envAssistantId,
    targetType,
    buildClient,
  ]);

  const updateThreadState = useCallback(
    async (threadId: string, values: Record<string, unknown>) => {
      const normalizedThreadId = threadId.trim();
      if (!normalizedThreadId) {
        throw new Error("Thread id is required");
      }

      const client = buildClient();
      if (!client) {
        throw new Error("API URL is not configured");
      }

      await client.threads.updateState(normalizedThreadId, { values });
    },
    [buildClient],
  );

  const value = {
    getThreads,
    updateThreadState,
    threads,
    setThreads,
    threadsLoading,
    setThreadsLoading,
  };

  return (
    <ThreadContext.Provider value={value}>{children}</ThreadContext.Provider>
  );
}

export function useThreads() {
  const context = useContext(ThreadContext);
  if (context === undefined) {
    throw new Error("useThreads must be used within a ThreadProvider");
  }
  return context;
}
