const LOCAL_PLATFORM_API_URL = "http://localhost:2024";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

function isLoopbackHost(hostname: string): boolean {
  return LOOPBACK_HOSTS.has(hostname.trim().toLowerCase());
}

function parseUrl(raw: string): URL | null {
  try {
    return new URL(raw);
  } catch {
    return null;
  }
}

export function isLoopbackUrl(raw: string | null | undefined): boolean {
  const value = raw?.trim();
  if (!value) {
    return false;
  }

  const parsed = parseUrl(value);
  if (parsed) {
    return isLoopbackHost(parsed.hostname);
  }

  return value.includes("localhost") || value.includes("127.0.0.1") || value.includes("::1");
}

function inferPlatformApiUrlFromWindow(): string {
  if (typeof window === "undefined") {
    return LOCAL_PLATFORM_API_URL;
  }

  const hostname = window.location.hostname.trim().toLowerCase();
  if (!hostname || isLoopbackHost(hostname)) {
    return LOCAL_PLATFORM_API_URL;
  }

  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  return `${protocol}//${hostname}:2024`;
}

export function getConfiguredPlatformApiUrl(): string {
  return (
    process.env.NEXT_PUBLIC_PLATFORM_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    inferPlatformApiUrlFromWindow()
  );
}

export function getStoredOrConfiguredPlatformApiUrl(
  storageKey = "lg:platform:apiUrl",
): string {
  if (typeof window === "undefined") {
    return getConfiguredPlatformApiUrl();
  }

  const preferred = getConfiguredPlatformApiUrl();
  const stored = window.localStorage.getItem(storageKey)?.trim();

  if (!stored) {
    return preferred;
  }

  if (isLoopbackUrl(stored) && !isLoopbackUrl(preferred)) {
    return preferred;
  }

  return stored;
}

export function syncPlatformApiUrlStorage(): void {
  if (typeof window === "undefined") {
    return;
  }

  const preferred = getConfiguredPlatformApiUrl();
  const platformApiUrl = window.localStorage.getItem("lg:platform:apiUrl")?.trim();
  const chatApiUrl = window.localStorage.getItem("lg:chat:apiUrl")?.trim();

  if (!platformApiUrl || (isLoopbackUrl(platformApiUrl) && !isLoopbackUrl(preferred))) {
    window.localStorage.setItem("lg:platform:apiUrl", preferred);
  }

  if (!chatApiUrl || (isLoopbackUrl(chatApiUrl) && !isLoopbackUrl(preferred))) {
    window.localStorage.setItem("lg:chat:apiUrl", preferred);
  }
}
