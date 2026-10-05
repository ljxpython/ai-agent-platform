import { Client } from "@langchain/langgraph-sdk";
import {
  platformApiBaseUrl,
  refreshAccessToken,
  resolveAuthorizedAccessToken,
} from "@/services/http/client";
import { getAccessToken, getSessionGeneration } from "@/services/auth/token";
import {
  handleSessionExpired,
  hasStoredSession,
} from "@/services/auth/session-expiry";
import { formatPlatformHttpErrorMessage } from "@/utils/http-error";
import { notifyAccessDenied } from "@/services/auth/access-events";

function getLanggraphApiUrl() {
  const normalizedBase = platformApiBaseUrl.replace(/\/+$/, "");
  const path = normalizedBase.endsWith("/api/langgraph")
    ? normalizedBase
    : `${normalizedBase}/api/langgraph`;
  return new URL(path, window.location.origin).toString().replace(/\/+$/, "");
}

type LanggraphAuthorizedFetchOptions = {
  fetchImpl?: typeof fetch;
  getAccessToken?: () => string;
  refreshAccessToken?: () => Promise<string>;
  hasStoredSession?: () => boolean;
  onSessionExpired?: () => void;
};

function withAccessToken(
  init: RequestInit | undefined,
  accessToken: string,
): RequestInit {
  const headers = new Headers(init?.headers);
  const normalizedToken = accessToken.trim();

  if (normalizedToken) {
    headers.set("Authorization", `Bearer ${normalizedToken}`);
  } else {
    headers.delete("Authorization");
  }

  return {
    ...init,
    headers,
  };
}

function requiresCommandIdempotencyKey(
  input: RequestInfo | URL,
  init?: RequestInit,
): boolean {
  const method = (
    init?.method || (input instanceof Request ? input.method : "GET")
  ).toUpperCase();
  if (method !== "POST") {
    return false;
  }

  const url = input instanceof Request ? input.url : input.toString();
  return /^\/api\/langgraph\/threads\/[^/]+\/commands\/?$/.test(
    new URL(url, "http://localhost").pathname,
  );
}

function withCommandIdempotencyKey(
  input: RequestInfo | URL,
  init?: RequestInit,
): RequestInit | undefined {
  if (!requiresCommandIdempotencyKey(input, init)) {
    return init;
  }

  const headers = new Headers(init?.headers);
  if (!headers.has("Idempotency-Key")) {
    headers.set(
      "Idempotency-Key",
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? `run:${crypto.randomUUID()}`
        : `run:${Date.now()}:${Math.random().toString(16).slice(2)}`,
    );
  }

  return {
    ...init,
    headers,
  };
}

async function normalizeProtocolErrorResponse(
  response: Response,
): Promise<Response> {
  if (response.ok) {
    return response;
  }

  try {
    const payload = (await response.clone().json()) as Record<string, unknown>;
    const errorBody = payload.error;
    if (
      errorBody &&
      typeof errorBody === "object" &&
      !Array.isArray(errorBody)
    ) {
      const body = errorBody as Record<string, unknown>;
      const message = typeof body.message === "string" ? body.message : "";
      const code = typeof body.code === "string" ? body.code : "";
      if (message) {
        const safeMessage = formatPlatformHttpErrorMessage({
          response: { status: response.status, data: payload },
        });
        const headers = new Headers(response.headers);
        headers.delete("content-length");
        headers.delete("content-encoding");
        headers.delete("transfer-encoding");
        return new Response(
          JSON.stringify({
            ...payload,
            message: safeMessage,
            code,
            error: body,
          }),
          {
            status: response.status,
            statusText: response.statusText,
            headers,
          },
        );
      }
    }
  } catch {
    // Preserve the original response when the body is not JSON.
  }

  return response;
}

async function normalizeStreamHandshake(
  input: RequestInfo | URL,
  response: Response,
): Promise<Response> {
  const path = new URL(
    input instanceof Request ? input.url : input.toString(),
    "http://localhost",
  ).pathname;
  if (
    !/\/threads\/[^/]+\/(?:stream\/events|runs\/stream|runs\/[^/]+\/stream)\/?$/.test(
      path,
    ) ||
    response.ok
  ) {
    return response;
  }
  const normalized = response;
  let code: string | undefined;
  let requestId: string | undefined;
  try {
    const body = (await normalized.clone().json()) as {
      error?: { code?: string; request_id?: string };
      request_id?: string;
    };
    code = body.error?.code;
    requestId = body.request_id ?? body.error?.request_id;
  } catch {
    // A non-JSON upstream body is never used as a user-facing error.
  }
  const error = new Error(
    formatPlatformHttpErrorMessage({ response: { status: normalized.status } }),
  ) as Error & {
    status: number;
    code?: string;
    request_id?: string;
    retryAfter?: string | null;
  };
  error.status = normalized.status;
  error.code = code;
  error.request_id = requestId;
  error.retryAfter = normalized.headers.get("retry-after");
  throw error;
}

export function createLanggraphAuthorizedFetch(
  options: LanggraphAuthorizedFetchOptions = {},
) {
  const generation = getSessionGeneration();
  const fetchImpl = options.fetchImpl ?? fetch;
  const readAccessToken = options.getAccessToken ?? getAccessToken;
  const renewAccessToken = options.refreshAccessToken ?? refreshAccessToken;
  const readStoredSession = options.hasStoredSession ?? hasStoredSession;
  const expireSession = options.onSessionExpired ?? handleSessionExpired;

  async function normalize(
    input: RequestInfo | URL,
    init: RequestInit | undefined,
    response: Response,
  ) {
    if (response.status === 403 && typeof window !== "undefined") {
      let code: string | undefined;
      try {
        code = (await response.clone().json()).error?.code;
      } catch {
        /* 非 JSON 拒绝仍按请求作用域处理。 */
      }
      notifyAccessDenied(
        input instanceof Request ? input.url : input.toString(),
        init?.method || (input instanceof Request ? input.method : "GET"),
        new Headers(init?.headers).get("x-project-id"),
        code,
      );
    }
    return normalizeStreamHandshake(
      input,
      await normalizeProtocolErrorResponse(response),
    );
  }

  return async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    if (generation !== getSessionGeneration())
      throw new Error("登录会话已变更");
    const headers = new Headers(
      input instanceof Request ? input.headers : undefined,
    );
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    const requestInit = withCommandIdempotencyKey(input, { ...init, headers });
    let initialToken =
      (await resolveAuthorizedAccessToken()).trim() || readAccessToken().trim();
    if (!initialToken && readStoredSession()) {
      initialToken = (await renewAccessToken()).trim();
      if (!initialToken) {
        throw new Error("暂时无法恢复登录连接，请稍后重试");
      }
    }
    if (generation !== getSessionGeneration())
      throw new Error("登录会话已变更");
    const initialResponse = await fetchImpl(
      input,
      withAccessToken(requestInit, initialToken),
    );
    if (generation !== getSessionGeneration())
      throw new Error("登录会话已变更");
    if (initialResponse.status !== 401) {
      return normalize(input, requestInit, initialResponse);
    }

    const nextAccessToken = (await renewAccessToken()).trim();
    if (generation !== getSessionGeneration())
      throw new Error("登录会话已变更");
    if (!nextAccessToken) {
      return normalize(input, requestInit, initialResponse);
    }

    const retryResponse = await fetchImpl(
      input,
      withAccessToken(requestInit, nextAccessToken),
    );
    if (generation !== getSessionGeneration())
      throw new Error("登录会话已变更");
    if (retryResponse.status === 401 && readStoredSession()) {
      expireSession();
    }

    return normalize(input, requestInit, retryResponse);
  };
}

export function createLanggraphClient(projectId?: string): Client {
  const normalizedProjectId = projectId?.trim() || "";

  return new Client({
    apiUrl: getLanggraphApiUrl(),
    callerOptions: {
      fetch: createLanggraphAuthorizedFetch(),
      maxRetries: 0,
    },
    defaultHeaders: {
      ...(normalizedProjectId ? { "x-project-id": normalizedProjectId } : {}),
    },
  });
}

export { getLanggraphApiUrl };
