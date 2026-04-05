export function getApiKey(): string | null {
  try {
    if (typeof window === "undefined") return null;

    const chatApiKey = window.localStorage.getItem("lg:chat:apiKey") ?? null;
    if (chatApiKey) {
      return chatApiKey;
    }

    const rawTokenSet = window.localStorage.getItem("oidc:token_set");
    if (!rawTokenSet) {
      return null;
    }

    const parsedTokenSet = JSON.parse(rawTokenSet) as { access_token?: string };
    const accessToken =
      typeof parsedTokenSet?.access_token === "string"
        ? parsedTokenSet.access_token.trim()
        : "";
    if (!accessToken) {
      return null;
    }

    window.localStorage.setItem("lg:chat:apiKey", accessToken);
    return accessToken;
  } catch {
    // no-op
  }

  return null;
}
