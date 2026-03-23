import { getValidAccessToken } from "@/lib/oidc-storage";

type ApiClientOptions = {
  headers?: Record<string, string>;
  requireAuth?: boolean;
};


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
    return this.parse<T>(response);
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
    return this.parse<T>(response);
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
    return this.parse<T>(response);
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
    return this.parse<T>(response);
  }

  async del<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.defaultHeaders,
    });
    return this.parse<T>(response);
  }

  private async parse<T>(response: Response): Promise<T> {
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
  const baseUrl =
    process.env.NEXT_PUBLIC_PLATFORM_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" ? window.localStorage.getItem("lg:platform:apiUrl") : null) ||
    "http://localhost:2024";

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
