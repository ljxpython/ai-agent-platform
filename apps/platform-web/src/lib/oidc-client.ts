const OIDC_STATE_KEY = "oidc:pkce_state";
const OIDC_VERIFIER_KEY = "oidc:pkce_verifier";
const OIDC_RETURN_TO_KEY = "oidc:return_to";

function b64UrlEncode(bytes: Uint8Array): string {
  const str = String.fromCharCode(...bytes);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function randomString(length = 64): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return b64UrlEncode(bytes).slice(0, length);
}

export async function createPkcePair() {
  const verifier = randomString(96);
  const input = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", input);
  const challenge = b64UrlEncode(new Uint8Array(digest));
  return { verifier, challenge };
}

export function getKeycloakIssuerFromClient(): string {
  const issuer = process.env.NEXT_PUBLIC_KEYCLOAK_ISSUER;
  if (issuer) return issuer.replace(/\/$/, "");

  const base = process.env.NEXT_PUBLIC_KEYCLOAK_BASE_URL ?? "http://127.0.0.1:18080";
  const realm = process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "agent-platform";
  return `${base.replace(/\/$/, "")}/realms/${realm}`;
}

export function getOidcClientIdFromClient(): string {
  return process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "agent-proxy";
}

export async function startOidcLogin(returnTo = "/workspace/chat") {
  const issuer = getKeycloakIssuerFromClient();
  const clientId = getOidcClientIdFromClient();
  const redirectUri = `${window.location.origin}/auth/callback`;

  const { verifier, challenge } = await createPkcePair();
  const state = randomString(48);

  window.sessionStorage.setItem(OIDC_STATE_KEY, state);
  window.sessionStorage.setItem(OIDC_VERIFIER_KEY, verifier);
  window.sessionStorage.setItem(OIDC_RETURN_TO_KEY, returnTo);

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid profile email",
    code_challenge: challenge,
    code_challenge_method: "S256",
    state,
  });

  window.location.href = `${issuer}/protocol/openid-connect/auth?${params.toString()}`;
}

export function consumePkceSession() {
  const state = window.sessionStorage.getItem(OIDC_STATE_KEY);
  const verifier = window.sessionStorage.getItem(OIDC_VERIFIER_KEY);
  const returnTo = window.sessionStorage.getItem(OIDC_RETURN_TO_KEY) ?? "/workspace/chat";

  window.sessionStorage.removeItem(OIDC_STATE_KEY);
  window.sessionStorage.removeItem(OIDC_VERIFIER_KEY);
  window.sessionStorage.removeItem(OIDC_RETURN_TO_KEY);

  return { state, verifier, returnTo };
}

export function buildLogoutUrl(postLogoutRedirectUri: string): string {
  const issuer = getKeycloakIssuerFromClient();
  const clientId = getOidcClientIdFromClient();
  const params = new URLSearchParams({
    client_id: clientId,
    post_logout_redirect_uri: postLogoutRedirectUri,
  });
  return `${issuer}/protocol/openid-connect/logout?${params.toString()}`;
}
