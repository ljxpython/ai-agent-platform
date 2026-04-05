export type ChatTargetType = "assistant" | "graph";

export type ChatTargetPreference = {
  targetType: ChatTargetType;
  assistantId?: string;
  graphId?: string;
  updatedAt: string;
};

type ChatTargetInput = {
  targetType?: string | null;
  assistantId?: string | null;
  graphId?: string | null;
  updatedAt?: string | null;
};

type SearchParamReader = {
  get: (name: string) => string | null;
};

const STORAGE_KEY_PREFIX = "platform-web-v2:chat-target:";

function getStorageKey(projectId: string) {
  return `${STORAGE_KEY_PREFIX}${projectId}`;
}

export function normalizeChatTarget(
  input?: ChatTargetInput | null,
): ChatTargetPreference | null {
  if (!input) {
    return null;
  }

  const targetType = input.targetType === "graph" ? "graph" : "assistant";
  const assistantId = input.assistantId?.trim() || "";
  const graphId = input.graphId?.trim() || "";
  const updatedAt = input.updatedAt?.trim() || new Date().toISOString();

  if (targetType === "graph") {
    const resolvedGraphId = graphId || assistantId;
    if (!resolvedGraphId) {
      return null;
    }
    return {
      targetType,
      graphId: resolvedGraphId,
      updatedAt,
    };
  }

  if (!assistantId) {
    return null;
  }

  return {
    targetType,
    assistantId,
    updatedAt,
  };
}

export function parseChatTargetSearchParams(
  searchParams: SearchParamReader,
): ChatTargetPreference | null {
  return normalizeChatTarget({
    targetType: searchParams.get("targetType"),
    assistantId: searchParams.get("assistantId"),
    graphId: searchParams.get("graphId"),
  });
}

export function applyChatTargetToSearchParams(
  params: URLSearchParams,
  input: ChatTargetInput,
) {
  const target = normalizeChatTarget(input);
  if (!target) {
    params.delete("targetType");
    params.delete("assistantId");
    params.delete("graphId");
    return params;
  }

  params.set("targetType", target.targetType);
  if (target.targetType === "graph") {
    params.set("graphId", target.graphId || "");
    params.delete("assistantId");
    return params;
  }

  params.set("assistantId", target.assistantId || "");
  params.delete("graphId");
  return params;
}

export function buildChatHref(options: {
  projectId?: string;
  threadId?: string;
  apiUrl?: string;
  target: ChatTargetInput;
  extraParams?: Record<string, string | null | undefined>;
}) {
  const params = new URLSearchParams();
  if (options.projectId?.trim()) {
    params.set("projectId", options.projectId.trim());
  }
  if (options.threadId?.trim()) {
    params.set("threadId", options.threadId.trim());
  }
  if (options.apiUrl?.trim()) {
    params.set("apiUrl", options.apiUrl.trim());
  }
  applyChatTargetToSearchParams(params, options.target);

  for (const [key, value] of Object.entries(options.extraParams ?? {})) {
    if (value?.trim()) {
      params.set(key, value.trim());
    }
  }

  const query = params.toString();
  return query ? `/workspace/chat?${query}` : "/workspace/chat";
}

export function readRecentChatTarget(
  projectId: string,
): ChatTargetPreference | null {
  if (!projectId.trim() || typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(getStorageKey(projectId));
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as ChatTargetInput;
    const normalized = normalizeChatTarget(parsed);
    if (!normalized) {
      window.localStorage.removeItem(getStorageKey(projectId));
      return null;
    }
    return normalized;
  } catch {
    window.localStorage.removeItem(getStorageKey(projectId));
    return null;
  }
}

export function writeRecentChatTarget(
  projectId: string,
  input: ChatTargetInput,
) {
  if (!projectId.trim() || typeof window === "undefined") {
    return;
  }

  const target = normalizeChatTarget(input);
  if (!target) {
    return;
  }

  window.localStorage.setItem(getStorageKey(projectId), JSON.stringify(target));
}

export function clearRecentChatTarget(projectId: string) {
  if (!projectId.trim() || typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(getStorageKey(projectId));
}
