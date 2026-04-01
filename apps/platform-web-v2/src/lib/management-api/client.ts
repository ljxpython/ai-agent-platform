import {
  clearOidcTokenSet,
  ensureValidAccessToken,
  getValidAccessToken,
  getOidcTokenSet,
} from "@/lib/oidc-storage";
import { getStoredOrConfiguredPlatformApiUrl } from "@/lib/platform-api-url";

type ApiClientOptions = {
  headers?: Record<string, string>;
  requireAuth?: boolean;
};

function redirectToLogin(): void {
  if (typeof window === "undefined") {
    return;
  }

  const currentPath = `${window.location.pathname}${window.location.search}`;
  const params = new URLSearchParams();
  params.set("redirect", currentPath);
  window.location.replace(`/auth/login?${params.toString()}`);
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

  async del<T>(path: string): Promise<T> {
    const response = await this.request(path, { method: "DELETE" });
    return this.parseJson<T>(response);
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
      const refreshedToken = await ensureValidAccessToken({
        baseUrl: this.baseUrl,
        forceRefresh: true,
      });
      if (refreshedToken) {
        const retryHeaders = await this.buildHeaders(Boolean(init.body), true);
        return fetch(`${this.baseUrl}${path}`, {
          ...init,
          headers: retryHeaders,
        });
      }

      clearOidcTokenSet();
      redirectToLogin();
    }

    return response;
  }

  private async buildHeaders(
    includeJsonContentType: boolean,
    forceRefresh = false,
  ): Promise<Record<string, string>> {
    const headers: Record<string, string> = { ...this.defaultHeaders };
    if (includeJsonContentType) {
      headers["Content-Type"] = "application/json";
    }
    if (!this.requireAuth) {
      return headers;
    }

    const token = forceRefresh
      ? await ensureValidAccessToken({ baseUrl: this.baseUrl, forceRefresh: true })
      : await ensureValidAccessToken({ baseUrl: this.baseUrl });
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
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
}

export function createManagementApiClient(options?: ApiClientOptions): ManagementApiClient | null {
  const baseUrl = getStoredOrConfiguredPlatformApiUrl();
  if (!baseUrl) {
    return null;
  }

  const requireAuth = options?.requireAuth ?? true;
  const tokenSet = getOidcTokenSet();
  const token = getValidAccessToken();

  if (requireAuth && !token && !tokenSet?.refresh_token) {
    return null;
  }

  return new ManagementApiClient(baseUrl.replace(/\/+$/, ""), options?.headers || {}, requireAuth);
}
