import {
  createContext,
  type FC,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { Label } from "@/components/ui/label";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { getApiKey } from "@/lib/api-key";
import { logClient } from "@/lib/client-logger";
import { getConfiguredPlatformApiUrl } from "@/lib/platform-api-url";
import { isJwtToken } from "@/lib/token";
import { useThreads } from "./Thread";
import { useWorkspaceContext } from "./WorkspaceContext";
import { toast } from "sonner";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  authHeaders: Record<string, string>,
): Promise<boolean> {
  try {
    const res = await fetch(`${apiUrl}/info`, {
      headers: authHeaders,
    });

    return res.ok;
  } catch (e) {
    await logClient({
      level: "error",
      event: "stream_check_graph_status_error",
      message: "Failed to check graph status",
      context: {
        apiUrl,
        error: String(e),
      },
    });
    return false;
  }
}

async function fetchGraphs(
  apiUrl: string,
  authHeaders: Record<string, string>,
): Promise<Array<{ graph_id: string; description?: string }>> {
  try {
    const response = await fetch(`${apiUrl}/graphs/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
      },
      body: JSON.stringify({ limit: 200, offset: 0 }),
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    const payload = (await response.json()) as {
      items?: Array<{ graph_id?: string; description?: string | null }>;
    };
    if (!Array.isArray(payload.items)) {
      return [];
    }

    return payload.items.reduce<Array<{ graph_id: string; description?: string }>>((acc, item) => {
      const graphId = typeof item?.graph_id === "string" ? item.graph_id : "";
      if (!graphId) {
        return acc;
      }
      acc.push({
        graph_id: graphId,
        description: typeof item?.description === "string" ? item.description : undefined,
      });
      return acc;
    }, []);
  } catch {
    return [];
  }
}

type AssistantOption = {
  assistant_id: string;
  name?: string | null;
};

type GraphOption = {
  graph_id: string;
  description?: string;
};

async function fetchAssistants(
  apiUrl: string,
  authHeaders: Record<string, string>,
): Promise<AssistantOption[]> {
  try {
    const response = await fetch(`${apiUrl}/assistants/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
      },
      body: JSON.stringify({ limit: 200, offset: 0 }),
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    const payload = (await response.json()) as
      | Array<{ assistant_id?: string; name?: string | null }>
      | {
          items?: Array<{ assistant_id?: string; name?: string | null }>;
        };

    const rows = Array.isArray(payload)
      ? payload
      : Array.isArray(payload.items)
        ? payload.items
        : [];

    return rows
      .map((item) => ({
        assistant_id:
          typeof item?.assistant_id === "string" ? item.assistant_id : "",
        name: typeof item?.name === "string" ? item.name : null,
      }))
      .filter((item) => item.assistant_id);
  } catch {
    return [];
  }
}

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
  projectId,
  autoTokenEnabled,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
  projectId: string;
  autoTokenEnabled: boolean;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads } = useThreads();
  const runtimeHeaders = useMemo<Record<string, string>>(
    () => ({
      ...(projectId ? { "x-project-id": projectId } : {}),
    }),
    [projectId],
  );

  const authHeaders = useMemo<Record<string, string>>(() => {
    if (isJwtToken(apiKey)) {
      return {
        Authorization: `Bearer ${apiKey}`,
        ...runtimeHeaders,
      };
    }

    if (apiKey && !autoTokenEnabled) {
      return {
        "X-Api-Key": apiKey,
        ...runtimeHeaders,
      };
    }

    return runtimeHeaders;
  }, [apiKey, runtimeHeaders, autoTokenEnabled]);

  const statusHeaders = useMemo<Record<string, string>>(() => {
    const headers: Record<string, string> = {};

    if (isJwtToken(apiKey)) {
      headers.Authorization = `Bearer ${apiKey}`;
    } else if (apiKey && !autoTokenEnabled) {
      headers["X-Api-Key"] = apiKey;
    }

    return headers;
  }, [apiKey, autoTokenEnabled]);

  const streamApiKey = isJwtToken(apiKey) ? undefined : apiKey ?? undefined;

  const streamValue = useTypedStream({
    apiUrl,
    apiKey: streamApiKey,
    defaultHeaders: authHeaders,
    assistantId,
    threadId: threadId || null,
    fetchStateHistory: true,
    onCustomEvent: (event, options) => {
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      logClient({
        level: "info",
        event: "stream_thread_id_changed",
        message: "Thread id updated from stream callback",
        context: {
          threadId: id,
          assistantId,
        },
      });
      sleep().then(() =>
        getThreads()
          .then(setThreads)
          .catch((error) =>
            logClient({
              level: "error",
              event: "stream_refresh_threads_error",
              message: "Failed to refresh threads after thread id change",
              context: {
                threadId: id,
                error: String(error),
              },
            }),
          ),
      );
    },
  });

  useEffect(() => {
    checkGraphStatus(apiUrl, statusHeaders).then((ok) => {
      if (!ok) {
        logClient({
          level: "warn",
          event: "stream_graph_status_unhealthy",
          message: "Graph status check failed",
          context: {
            apiUrl,
            assistantId,
          },
        });
        toast.error("Failed to connect to LangGraph server", {
          description: () => (
            <p>
              Please ensure your graph is running at <code>{apiUrl}</code> and
              your API key is correctly set (if connecting to a deployed graph).
            </p>
          ),
          duration: 10000,
          richColors: true,
          closeButton: true,
        });
      }
    });
  }, [apiUrl, assistantId, statusHeaders]);

  return (
    <StreamContext.Provider value={streamValue}>
      {children}
    </StreamContext.Provider>
  );
};

// Default values for the form
const DEFAULT_ASSISTANT_ID = "assistant";

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

export const StreamProvider: FC<{
  children: ReactNode;
  initialApiUrl?: string;
  initialAssistantId?: string;
  initialGraphId?: string;
  initialTargetType?: "assistant" | "graph";
  title?: string;
  description?: string;
  allowAssistantSwitch?: boolean;
  allowApiUrlEdit?: boolean;
}> = ({
  children,
  initialApiUrl,
  initialAssistantId,
  initialGraphId,
  initialTargetType,
  title,
  description,
  allowAssistantSwitch = true,
  allowApiUrlEdit = true,
}) => {
  const { projectId } = useWorkspaceContext();
  const autoTokenEnabled = false;

  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;

  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: initialApiUrl || envApiUrl || "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: initialAssistantId || envAssistantId || "",
  });
  const [graphId, setGraphId] = useQueryState("graphId", {
    defaultValue: initialGraphId || "",
  });
  const [targetType, setTargetType] = useQueryState("targetType", {
    defaultValue: initialTargetType || "assistant",
  });
  const normalizedTargetType = targetType === "graph" ? "graph" : "assistant";
  const [assistantOptions, setAssistantOptions] = useState<AssistantOption[]>([]);
  const [graphOptions, setGraphOptions] = useState<GraphOption[]>([]);
  const [isGraphOptionsLoading, setIsGraphOptionsLoading] = useState(false);

  const [apiKey, _setApiKey] = useState(() => {
    if (autoTokenEnabled) {
      return "";
    }
    const storedKey = getApiKey();
    return storedKey || "";
  });

  const setApiKey = useCallback((key: string) => {
    window.localStorage.setItem("lg:chat:apiKey", key);
    _setApiKey(key);
  }, []);

  useEffect(() => {
    if (!envAssistantId && assistantId === "agent") {
      setAssistantId(DEFAULT_ASSISTANT_ID);
      setGraphId("");
      logClient({
        level: "warn",
        event: "stream_assistant_id_migrated",
        message: "Migrated legacy assistantId 'agent' to 'assistant'",
      });
    }
  }, [assistantId, envAssistantId, setAssistantId, setGraphId]);

  useEffect(() => {
    if (!apiUrl) {
      return;
    }
    window.localStorage.setItem("lg:chat:apiUrl", apiUrl);
  }, [apiUrl]);

  useEffect(() => {
    if (!apiUrl) {
      return;
    }

    if (isDirectRuntimeUrl(apiUrl)) {
      const platformApiUrl = getConfiguredPlatformApiUrl();
      setApiUrl(platformApiUrl);
      logClient({
        level: "warn",
        event: "stream_runtime_url_rewritten",
        message: "Rewrote direct runtime URL to proxy URL for CORS-safe browser access",
        context: {
          from: apiUrl,
          to: platformApiUrl,
        },
      });
    }
  }, [apiUrl, setApiUrl]);

  // Determine final values to use, prioritizing URL params then env vars
  const normalizedApiUrl = normalizeApiUrl(apiUrl || envApiUrl || "", envApiUrl);
  const finalApiUrl = appendLangGraphApiPrefix(normalizedApiUrl);
  const finalAssistantId =
    normalizedTargetType === "graph"
      ? graphId || assistantId
      : assistantId || envAssistantId;

  const formStatusHeaders = useMemo<Record<string, string>>(() => {
    const headers: Record<string, string> = {};
    if (projectId) {
      headers["x-project-id"] = projectId;
    }
    if (isJwtToken(apiKey)) {
      headers.Authorization = `Bearer ${apiKey}`;
    } else if (apiKey) {
      headers["X-Api-Key"] = apiKey;
    }
    return headers;
  }, [projectId, apiKey]);

  useEffect(() => {
    if (finalApiUrl && finalAssistantId) {
      return;
    }

    if (!finalApiUrl) {
      setGraphOptions([]);
      return;
    }

    setIsGraphOptionsLoading(true);
    Promise.all([
      fetchAssistants(finalApiUrl, formStatusHeaders),
      fetchGraphs(finalApiUrl, formStatusHeaders),
    ])
      .then(([assistants, graphs]) => {
        setAssistantOptions(assistants);
        setGraphOptions(graphs);
      })
      .finally(() => {
        setIsGraphOptionsLoading(false);
      });
  }, [finalApiUrl, finalAssistantId, formStatusHeaders]);

  // Show the form if we: don't have an API URL, or don't have an assistant ID
  if (!finalApiUrl || !finalAssistantId) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4">
        <div className="animate-in fade-in-0 zoom-in-95 bg-background flex max-w-3xl flex-col rounded-lg border shadow-lg">
          <div className="mt-14 flex flex-col gap-2 border-b p-6">
              <div className="flex flex-col items-start gap-2">
                <LangGraphLogoSVG className="h-7" />
                <h1 className="text-xl font-semibold tracking-tight">
                  {title || "Agent Chat"}
                </h1>
              </div>
              <p className="text-muted-foreground">
                {description ||
                  "Welcome to Agent Chat! Before you get started, you need to enter the URL of the deployment and the assistant / graph ID."}
              </p>
            </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();

              const form = e.target as HTMLFormElement;
              const formData = new FormData(form);
              const apiUrl = formData.get("apiUrl") as string;
              const typeInput =
                (formData.get("targetType") as string) === "graph"
                  ? "graph"
                  : "assistant";
              const selectedAssistant =
                (formData.get("selectedAssistantId") as string) || "";
              const selectedGraph =
                (formData.get("selectedGraphId") as string) || "";
              const apiKey = formData.get("apiKey") as string;
              const resolvedAssistantId =
                typeInput === "graph"
                  ? selectedGraph.trim()
                  : selectedAssistant.trim();

              if (!resolvedAssistantId) {
                toast.error("Target ID is required", {
                  description: "Please select one assistant/graph from dropdown.",
                });
                return;
              }

              setApiUrl(apiUrl);
              setApiKey(apiKey);
                setTargetType(typeInput);
                if (typeInput === "graph") {
                  setGraphId(resolvedAssistantId);
                  setAssistantId("");
                } else {
                  setAssistantId(resolvedAssistantId);
                  setGraphId("");
                }

                form.reset();
              }}
            className="bg-muted/50 flex flex-col gap-6 p-6"
          >
            {allowApiUrlEdit ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="apiUrl">
                  Deployment URL<span className="text-rose-500">*</span>
                </Label>
                <p className="text-muted-foreground text-sm">
                  This is the URL of your LangGraph deployment. Can be a local, or
                  production deployment.
                </p>
                <Input
                  id="apiUrl"
                  name="apiUrl"
                  className="bg-background"
                  defaultValue={apiUrl || getConfiguredPlatformApiUrl()}
                  required
                />
              </div>
            ) : (
              <input
                type="hidden"
                name="apiUrl"
                value={apiUrl || getConfiguredPlatformApiUrl()}
              />
            )}

            {allowAssistantSwitch ? (
              <>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="targetType">
                    Target Type<span className="text-rose-500">*</span>
                  </Label>
                  <p className="text-muted-foreground text-sm">
                    Select exactly one target type for chat runs.
                  </p>
                  <select
                    id="targetType"
                    name="targetType"
                    className="bg-background border-input ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
                    value={normalizedTargetType}
                    onChange={(event) => {
                      const nextType = event.target.value === "graph" ? "graph" : "assistant";
                      setTargetType(nextType);
                    }}
                  >
                    <option value="assistant">Assistant</option>
                    <option value="graph">Graph</option>
                  </select>
                </div>

                {normalizedTargetType === "assistant" ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="selectedAssistantId">Assistant List</Label>
                <p className="text-muted-foreground text-sm">
                  Optional: pick from assistant options.
                </p>
                <select
                  id="selectedAssistantId"
                  name="selectedAssistantId"
                  className="bg-background border-input ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
                  defaultValue=""
                  required={normalizedTargetType === "assistant"}
                  disabled={
                    isGraphOptionsLoading || assistantOptions.length === 0
                  }
                >
                  <option value="">
                    {isGraphOptionsLoading
                      ? "Loading assistants..."
                      : assistantOptions.length > 0
                        ? "Select assistant"
                        : "No assistant options"}
                  </option>
                  {assistantOptions.map((assistant) => (
                    <option
                      key={assistant.assistant_id}
                      value={assistant.assistant_id}
                    >
                      {assistant.name?.trim()
                        ? `${assistant.name} (${assistant.assistant_id})`
                        : assistant.assistant_id}
                    </option>
                  ))}
                </select>
              </div>
                ) : (
              <div className="flex flex-col gap-2">
                <Label htmlFor="selectedGraphId">Graph List</Label>
                <p className="text-muted-foreground text-sm">
                  Optional: pick from graph options.
                </p>
                <select
                  id="selectedGraphId"
                  name="selectedGraphId"
                  className="bg-background border-input ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
                  defaultValue=""
                  required={normalizedTargetType === "graph"}
                  disabled={isGraphOptionsLoading || graphOptions.length === 0}
                >
                  <option value="">
                    {isGraphOptionsLoading
                      ? "Loading graphs..."
                      : graphOptions.length > 0
                        ? "Select graph"
                        : "No graph options"}
                  </option>
                  {graphOptions.map((graph) => (
                    <option
                      key={graph.graph_id}
                      value={graph.graph_id}
                    >
                      {graph.description?.trim()
                        ? `${graph.graph_id} — ${graph.description}`
                        : graph.graph_id}
                    </option>
                  ))}
                </select>
              </div>
                )}
              </>
            ) : (
              <>
                <input type="hidden" name="targetType" value={normalizedTargetType} />
                {normalizedTargetType === "graph" ? (
                  <input type="hidden" name="selectedGraphId" value={graphId || initialGraphId || assistantId || initialAssistantId || ""} />
                ) : (
                  <input type="hidden" name="selectedAssistantId" value={assistantId || initialAssistantId || ""} />
                )}
              </>
            )}

            <div className="flex flex-col gap-2">
              <Label htmlFor="apiKey">LangSmith API Key</Label>
              <p className="text-muted-foreground text-sm">
                This is <strong>NOT</strong> required if using a local LangGraph
                server. This value is stored in your browser's local storage and
                is only used to authenticate requests sent to your LangGraph
                server.
              </p>
              {autoTokenEnabled ? (
                <p className="text-xs text-emerald-700">
                  Auto token mode is enabled. The access token is filled
                  automatically by the current runtime configuration.
                </p>
              ) : null}
              <PasswordInput
                id="apiKey"
                name="apiKey"
                defaultValue={apiKey ?? ""}
                className="bg-background"
                placeholder="lsv2_pt_..."
              />
            </div>

            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                size="lg"
              >
                Continue
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <StreamSession
      apiKey={apiKey}
      apiUrl={finalApiUrl}
      assistantId={finalAssistantId}
      projectId={projectId}
      autoTokenEnabled={autoTokenEnabled}
    >
      {children}
    </StreamSession>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
};

export default StreamContext;
