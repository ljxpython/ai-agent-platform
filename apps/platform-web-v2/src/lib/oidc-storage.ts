import {
  getStoredOrConfiguredPlatformApiUrl,
  syncPlatformApiUrlStorage,
} from "@/lib/platform-api-url";

export type OidcTokenSet = {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_at?: number;
};

const OIDC_TOKEN_SET_KEY = "oidc:token_set";

let refreshAccessTokenPromise: Promise<string> | null = null;

function decodeBase64Url(raw: string): string {
  const normalized = raw.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  return atob(`${normalized}${padding}`);
}

function decodeJwtPayload<T>(token: string): T | null {
  const normalizedToken = token.trim();
  if (!normalizedToken) {
    return null;
  }

  const parts = normalizedToken.split(".");
  if (parts.length !== 3) {
    return null;
  }

  try {
    return JSON.parse(decodeBase64Url(parts[1])) as T;
  } catch {
    return null;
  }
}

export function getOidcTokenSet(): OidcTokenSet | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(OIDC_TOKEN_SET_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as OidcTokenSet;
  } catch {
    return null;
  }
}

export function getValidAccessToken(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const tokenSet = getOidcTokenSet();
  const accessToken = typeof tokenSet?.access_token === "string" ? tokenSet.access_token.trim() : "";
  const expiresAt = typeof tokenSet?.expires_at === "number" ? tokenSet.expires_at : null;

  if (!accessToken) {
    return "";
  }

  if (expiresAt && Date.now() >= expiresAt * 1000) {
    return "";
  }

  const parts = accessToken.split(".");
  if (parts.length === 3) {
    const payload = decodeJwtPayload<{ exp?: number }>(accessToken);
    if (!payload) {
      return "";
    }
    if (typeof payload.exp === "number" && Date.now() >= payload.exp * 1000) {
      return "";
    }
  }

  return accessToken;
}

export function hasOidcSession(): boolean {
  const tokenSet = getOidcTokenSet();
  return Boolean(tokenSet?.access_token || tokenSet?.refresh_token);
}

export function getOidcUserId(): string {
  const tokenSet = getOidcTokenSet();
  const tokens = [tokenSet?.access_token, tokenSet?.refresh_token];

  for (const token of tokens) {
    if (typeof token !== "string" || !token.trim()) {
      continue;
    }
    const payload = decodeJwtPayload<{ sub?: string }>(token);
    if (typeof payload?.sub === "string" && payload.sub.trim()) {
      return payload.sub.trim();
    }
  }

  return "";
}

export async function ensureValidAccessToken(options?: {
  baseUrl?: string;
  forceRefresh?: boolean;
}): Promise<string> {
  const forceRefresh = Boolean(options?.forceRefresh);
  if (!forceRefresh) {
    const accessToken = getValidAccessToken();
    if (accessToken) {
      return accessToken;
    }
  }

  const tokenSet = getOidcTokenSet();
  const refreshToken = tokenSet?.refresh_token?.trim() || "";
  if (!refreshToken) {
    clearOidcTokenSet();
    return "";
  }

  if (refreshAccessTokenPromise) {
    return refreshAccessTokenPromise;
  }

  const baseUrl =
    options?.baseUrl?.trim() || getStoredOrConfiguredPlatformApiUrl().trim();
  if (!baseUrl) {
    clearOidcTokenSet();
    return "";
  }

  refreshAccessTokenPromise = (async () => {
    try {
      const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/_management/auth/refresh`, {
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
      const nextAccessToken =
        typeof payload.access_token === "string"
          ? payload.access_token.trim()
          : "";
      const nextRefreshToken =
        typeof payload.refresh_token === "string"
          ? payload.refresh_token.trim()
          : "";

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

export async function ensureOidcSession(baseUrl?: string): Promise<boolean> {
  return Boolean(await ensureValidAccessToken({ baseUrl }));
}

export function setOidcTokenSet(tokenSet: OidcTokenSet): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(OIDC_TOKEN_SET_KEY, JSON.stringify(tokenSet));
  window.localStorage.setItem("lg:chat:apiKey", tokenSet.access_token);
}

export function ensureApiUrlSeeded(): void {
  syncPlatformApiUrlStorage();
}

export function clearOidcTokenSet(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(OIDC_TOKEN_SET_KEY);
  window.localStorage.removeItem("lg:chat:apiKey");
}
