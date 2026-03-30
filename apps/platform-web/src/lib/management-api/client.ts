import { getValidAccessToken } from "@/lib/oidc-storage";
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

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null;
  }
  const utf8Match = header.match(/filename\*\=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const plainMatch = header.match(/filename=\"?([^\";]+)\"?/i);
  return plainMatch?.[1] ?? null;
}


class ManagementApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly defaultHeaders: Record<string, string>,
  ) {}

  async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: this.defaultHeaders,
      cache: "no-store",
    });
    return this.parseJson<T>(response);
  }

  async post<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...this.defaultHeaders,
      },
      body: JSON.stringify(payload),
    });
    return this.parseJson<T>(response);
  }

  async patch<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...this.defaultHeaders,
      },
      body: JSON.stringify(payload),
    });
    return this.parseJson<T>(response);
  }

  async put<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...this.defaultHeaders,
      },
      body: JSON.stringify(payload),
    });
    return this.parseJson<T>(response);
  }

  async del<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.defaultHeaders,
    });
    return this.parseJson<T>(response);
  }

  async download(path: string): Promise<ManagementDownload> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: this.defaultHeaders,
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(await this.readError(response));
    }
    return {
      blob: await response.blob(),
      filename: parseContentDispositionFilename(response.headers.get("content-disposition")),
      contentType: response.headers.get("content-type"),
    };
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

  const token = getValidAccessToken();

  if ((options?.requireAuth ?? true) && !token) {
    return null;
  }

  const defaultHeaders: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options?.headers || {}),
  };

  return new ManagementApiClient(baseUrl.replace(/\/+$/, ""), defaultHeaders);
}
