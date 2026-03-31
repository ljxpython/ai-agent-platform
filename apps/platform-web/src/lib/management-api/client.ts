import {
  clearOidcTokenSet,
  getOidcTokenSet,
  getValidAccessToken,
  setOidcTokenSet,
} from "@/lib/oidc-storage";
import { getStoredOrConfiguredPlatformApiUrl } from "@/lib/platform-api-url";

type ApiClientOptions = {
  headers?: Record<string, string>;
  requireAuth?: boolean;
};

export type ManagementDownload = {
  blob: Blob;
  filename: string | null;
  contentType: string | null;
};

let refreshAccessTokenPromise: Promise<string> | null = null;

function redirectToLogin(): void {
  if (typeof window === "undefined") {
    return;
  }
  const currentPath = `${window.location.pathname}${window.location.search}`;
  const params = new URLSearchParams();
  params.set("redirect", currentPath);
  window.location.replace(`/auth/login?${params.toString()}`);
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null;
  }
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? null;
}


class ManagementApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly defaultHeaders: Record<string, string>,
    private readonly requireAuth: boolean,
  ) {}

  async get<T>(path: string): Promise<T> {
    const response = await this.request(path, { method: "GET", cache: "no-store" });
    return this.parseJson<T>(response);
  }

  async post<T>(path: string, payload: unknown): Promise<T> {
    const response = await this.request(path, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return this.parseJson<T>(response);
  }

  async patch<T>(path: string, payload: unknown): Promise<T> {
    const response = await this.request(path, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    return this.parseJson<T>(response);
  }

  async put<T>(path: string, payload: unknown): Promise<T> {
    const response = await this.request(path, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    return this.parseJson<T>(response);
  }

  async del<T>(path: string): Promise<T> {
    const response = await this.request(path, { method: "DELETE" });
    return this.parseJson<T>(response);
  }

  async download(path: string): Promise<ManagementDownload> {
    const response = await this.request(path, { method: "GET", cache: "no-store" });
    if (!response.ok) {
      throw new Error(await this.readError(response));
    }
    return {
      blob: await response.blob(),
      filename: parseContentDispositionFilename(response.headers.get("content-disposition")),
      contentType: response.headers.get("content-type"),
    };
  }

  private async request(path: string, init: RequestInit, allowRetry = true): Promise<Response> {
    const headers = await this.buildHeaders(Boolean(init.body));
    if (this.requireAuth && !headers.Authorization) {
      redirectToLogin();
      throw new Error("unauthorized");
    }
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });

    if (response.status === 401 && allowRetry && this.requireAuth) {
      const refreshedToken = await this.refreshAccessToken();
      if (refreshedToken) {
        const retryHeaders = await this.buildHeaders(Boolean(init.body), true);
        const retryResponse = await fetch(`${this.baseUrl}${path}`, {
          ...init,
          headers: retryHeaders,
        });
        if (retryResponse.status === 401) {
          clearOidcTokenSet();
          redirectToLogin();
        }
        return retryResponse;
      }
      redirectToLogin();
    }

    return response;
  }

  private async buildHeaders(includeJsonContentType: boolean, forceRefresh = false): Promise<Record<string, string>> {
    const headers: Record<string, string> = { ...this.defaultHeaders };
    if (includeJsonContentType) {
      headers["Content-Type"] = "application/json";
    }
    if (!this.requireAuth) {
      return headers;
    }

    const token = forceRefresh ? await this.refreshAccessToken() : await this.getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    } else {
      delete headers.Authorization;
    }
    return headers;
  }

  private async getAccessToken(): Promise<string> {
    const accessToken = getValidAccessToken();
    if (accessToken) {
      return accessToken;
    }

    const tokenSet = getOidcTokenSet();
    if (!tokenSet?.refresh_token) {
      return "";
    }
    return this.refreshAccessToken();
  }

  private async refreshAccessToken(): Promise<string> {
    if (refreshAccessTokenPromise) {
      return refreshAccessTokenPromise;
    }

    const tokenSet = getOidcTokenSet();
    const refreshToken = tokenSet?.refresh_token?.trim() || "";
    if (!refreshToken) {
      return "";
    }

    refreshAccessTokenPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}/_management/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
          clearOidcTokenSet();
          return "";
        }
        const payload = (await response.json()) as {
          access_token?: string;
          refresh_token?: string;
        };
        const nextAccessToken = typeof payload.access_token === "string" ? payload.access_token.trim() : "";
        const nextRefreshToken = typeof payload.refresh_token === "string" ? payload.refresh_token.trim() : "";
        if (!nextAccessToken || !nextRefreshToken) {
          clearOidcTokenSet();
          return "";
        }
        setOidcTokenSet({
          access_token: nextAccessToken,
          refresh_token: nextRefreshToken,
        });
        return nextAccessToken;
      } catch {
        clearOidcTokenSet();
        return "";
      } finally {
        refreshAccessTokenPromise = null;
      }
    })();

    return refreshAccessTokenPromise;
  }

  private async parseJson<T>(response: Response): Promise<T> {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail =
        typeof payload?.detail === "string"
          ? payload.detail
          : typeof payload?.error === "string"
            ? payload.error
            : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return payload as T;
  }

  private async readError(response: Response): Promise<string> {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => ({}));
      if (typeof payload?.detail === "string") {
        return payload.detail;
      }
      if (typeof payload?.error === "string") {
        return payload.error;
      }
    }
    const text = await response.text().catch(() => "");
    return text || `HTTP ${response.status}`;
  }
}


export function createManagementApiClient(options?: ApiClientOptions): ManagementApiClient | null {
  const baseUrl =
    getStoredOrConfiguredPlatformApiUrl();

  if (!baseUrl) {
    return null;
  }

  const requireAuth = options?.requireAuth ?? true;
  const tokenSet = getOidcTokenSet();
  const token = getValidAccessToken();

  if (requireAuth && !token && !tokenSet?.refresh_token) {
    return null;
  }

  const defaultHeaders: Record<string, string> = {
    ...(options?.headers || {}),
  };

  return new ManagementApiClient(baseUrl.replace(/\/+$/, ""), defaultHeaders, requireAuth);
}
