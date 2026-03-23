export type OidcTokenSet = {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_at?: number;
};

const OIDC_TOKEN_SET_KEY = "oidc:token_set";
const DEFAULT_API_URL = "http://localhost:2024";

function decodeBase64Url(raw: string): string {
  const normalized = raw.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  return atob(`${normalized}${padding}`);
}

export function getOidcTokenSet(): OidcTokenSet | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(OIDC_TOKEN_SET_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as OidcTokenSet;
  } catch {
    return null;
  }
}

export function getValidAccessToken(): string {
  if (typeof window === "undefined") return "";
  const tokenSet = getOidcTokenSet();
  const accessToken = typeof tokenSet?.access_token === "string" ? tokenSet.access_token.trim() : "";
  const expiresAt = typeof tokenSet?.expires_at === "number" ? tokenSet.expires_at : null;

  if (!accessToken) {
    return "";
  }

  if (expiresAt && Date.now() >= expiresAt * 1000) {
    clearOidcTokenSet();
    return "";
  }

  const parts = accessToken.split(".");
  if (parts.length === 3) {
    try {
      const payload = JSON.parse(decodeBase64Url(parts[1])) as { exp?: number };
      if (typeof payload.exp === "number" && Date.now() >= payload.exp * 1000) {
        clearOidcTokenSet();
        return "";
      }
    } catch {
      clearOidcTokenSet();
      return "";
    }
  }

  return accessToken;
}

export function setOidcTokenSet(tokenSet: OidcTokenSet): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(OIDC_TOKEN_SET_KEY, JSON.stringify(tokenSet));
  window.localStorage.setItem("lg:chat:apiKey", tokenSet.access_token);
}

export function ensureApiUrlSeeded(): void {
  if (typeof window === "undefined") return;

  const existingPlatformApiUrl = window.localStorage.getItem("lg:platform:apiUrl")?.trim();
  const existingChatApiUrl = window.localStorage.getItem("lg:chat:apiUrl")?.trim();
  if (existingPlatformApiUrl || existingChatApiUrl) {
    return;
  }

  const preferred =
    process.env.NEXT_PUBLIC_PLATFORM_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    DEFAULT_API_URL;

  window.localStorage.setItem("lg:platform:apiUrl", preferred);
  window.localStorage.setItem("lg:chat:apiUrl", preferred);
}

export function clearOidcTokenSet(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(OIDC_TOKEN_SET_KEY);
  window.localStorage.removeItem("lg:chat:apiKey");
}
