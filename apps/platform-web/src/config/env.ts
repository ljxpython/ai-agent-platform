import { z } from "zod";

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function isLoopbackHostname(hostname: string): boolean {
  return (
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]"
  );
}

function normalizeApiBaseUrl(value: string | undefined): string {
  const normalized = (value || "/").trim();
  if (!normalized || normalized === "/") {
    return "";
  }

  if (normalized.startsWith("/")) {
    return normalized === "/" ? "" : stripTrailingSlash(normalized);
  }

  return stripTrailingSlash(normalized);
}

type ResolveBrowserApiBaseUrlOptions = {
  preferSameOriginLoopbackProxy?: boolean;
};

export function resolveBrowserApiBaseUrl(
  value: string | undefined,
  options: ResolveBrowserApiBaseUrlOptions = {},
): string {
  const normalized = normalizeApiBaseUrl(value);
  if (typeof window === "undefined") {
    return normalized;
  }

  const preferSameOriginLoopbackProxy =
    options.preferSameOriginLoopbackProxy ?? import.meta.env.DEV;

  try {
    if (!normalized) {
      return stripTrailingSlash(
        new URL("/", window.location.origin).toString(),
      );
    }

    const configuredUrl = new URL(normalized, window.location.origin);
    if (
      preferSameOriginLoopbackProxy &&
      /^https?:$/.test(configuredUrl.protocol) &&
      isLoopbackHostname(window.location.hostname) &&
      isLoopbackHostname(configuredUrl.hostname) &&
      configuredUrl.origin !== window.location.origin
    ) {
      // Only rewrite loopback API origins during Vite dev, where the proxy is
      // expected to terminate same-origin requests for the browser.
      const sameOriginPath =
        configuredUrl.pathname === "/"
          ? ""
          : stripTrailingSlash(configuredUrl.pathname);
      return `${stripTrailingSlash(window.location.origin)}${sameOriginPath}`;
    }

    return stripTrailingSlash(configuredUrl.toString());
  } catch {
    return normalized;
  }
}

type ResolveBrowserMlflowBaseUrlOptions = {
  locationOrigin?: string;
};

export function resolveBrowserMlflowBaseUrl(
  value: string | undefined,
  options: ResolveBrowserMlflowBaseUrlOptions = {},
): string {
  const normalized = (value || "").trim();

  // 1. 允许在浏览器运行时通过 window.__MLFLOW_BASE_URL__ 或 sessionStorage 动态覆盖排障
  let target = normalized;
  if (typeof window !== "undefined") {
    const override =
      (window as any).__MLFLOW_BASE_URL__ ||
      window.sessionStorage?.getItem("VITE_MLFLOW_BASE_URL");
    if (override !== null && override !== undefined && override !== "") {
      target = String(override).trim();
    }
  }

  if (!target) {
    target = "http://127.0.0.1:9128";
  }

  const origin =
    options.locationOrigin ||
    (typeof window !== "undefined" ? window.location.origin : undefined);

  if (!origin) {
    return stripTrailingSlash(target);
  }

  try {
    const configuredUrl = new URL(target, origin);
    const browserHostname = new URL(origin).hostname;

    // 当配置的目标是本地 loopback (localhost/127.0.0.1/[::1])，
    // 但是客户端浏览器访问的页面实际位于非 loopback 宿主（如云服务器 IP 49.233.222.54 或域名）时，
    // 智能将 loopback hostname 替换为当前浏览器访问的实际宿主，端口（如 9128）和协议保持不变。
    if (
      isLoopbackHostname(configuredUrl.hostname) &&
      browserHostname &&
      !isLoopbackHostname(browserHostname)
    ) {
      configuredUrl.hostname = browserHostname;
    }

    return stripTrailingSlash(configuredUrl.toString());
  } catch {
    return stripTrailingSlash(target);
  }
}

const envSchema = z.object({
  VITE_APP_NAME: z.string().min(1).default("Agent Platform"),
  VITE_PLATFORM_API_URL: z.string().min(1).default("/"),
  VITE_PLATFORM_API_RUNTIME_ENABLED: z.coerce.boolean().default(true),
  VITE_REQUEST_TIMEOUT_MS: z.coerce.number().int().positive().default(30000),
  VITE_DEV_PORT: z.coerce.number().int().positive().default(3000),
  VITE_DEV_PROXY_TARGET: z.string().url().default("http://localhost:2142"),
  VITE_LANGGRAPH_DEBUG_URL: z.string().optional().default(""),
  VITE_LANGFUSE_BASE_URL: z
    .string()
    .url()
    .default("https://jp.cloud.langfuse.com"),
  VITE_LANGFUSE_PROJECT_ID: z.string().optional().default(""),
  VITE_LANGFUSE_TRACE_URL_TEMPLATE: z.string().optional().default(""),
  VITE_TRACING_PROVIDER: z.string().default("mlflow"),
  VITE_MLFLOW_BASE_URL: z.string().default("http://127.0.0.1:9128"),
  VITE_MLFLOW_EXPERIMENT_ID: z.string().default("6"),
  VITE_MLFLOW_TRACE_URL_TEMPLATE: z.string().optional().default(""),
});

const parsed = envSchema.parse(import.meta.env);

export const env = {
  appName: parsed.VITE_APP_NAME,
  platformApiUrl: resolveBrowserApiBaseUrl(parsed.VITE_PLATFORM_API_URL),
  platformApiRuntimeEnabled: parsed.VITE_PLATFORM_API_RUNTIME_ENABLED,
  requestTimeoutMs: parsed.VITE_REQUEST_TIMEOUT_MS,
  devPort: parsed.VITE_DEV_PORT,
  devProxyTarget: stripTrailingSlash(parsed.VITE_DEV_PROXY_TARGET),
  langgraphDebugUrl: parsed.VITE_LANGGRAPH_DEBUG_URL.trim(),
  langfuseBaseUrl: stripTrailingSlash(parsed.VITE_LANGFUSE_BASE_URL),
  langfuseProjectId: (parsed.VITE_LANGFUSE_PROJECT_ID || "").trim(),
  langfuseTraceUrlTemplate: (
    parsed.VITE_LANGFUSE_TRACE_URL_TEMPLATE || ""
  ).trim(),
  get tracingProvider(): string {
    if (typeof window !== "undefined") {
      const override =
        (window as any).__TRACING_PROVIDER__ ||
        window.sessionStorage?.getItem("VITE_TRACING_PROVIDER");
      if (override !== null && override !== undefined && override !== "") {
        return String(override).trim().toLowerCase();
      }
    }
    return (parsed.VITE_TRACING_PROVIDER || "mlflow").trim().toLowerCase();
  },
  get mlflowBaseUrl(): string {
    return resolveBrowserMlflowBaseUrl(parsed.VITE_MLFLOW_BASE_URL);
  },
  mlflowExperimentId: (parsed.VITE_MLFLOW_EXPERIMENT_ID || "6").trim(),
  mlflowTraceUrlTemplate: (parsed.VITE_MLFLOW_TRACE_URL_TEMPLATE || "").trim(),
};
