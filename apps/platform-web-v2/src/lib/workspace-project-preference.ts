"use client";

import { getOidcUserId } from "@/lib/oidc-storage";
import { getStoredOrConfiguredPlatformApiUrl } from "@/lib/platform-api-url";

const WORKSPACE_PROJECT_PREFERENCE_PREFIX = "lg:workspace:lastProjectId";

function getWorkspaceProjectPreferenceKey(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const apiBase = getStoredOrConfiguredPlatformApiUrl().trim().replace(/\/+$/, "");
  const userId = getOidcUserId().trim();
  if (!apiBase || !userId) {
    return "";
  }

  return `${WORKSPACE_PROJECT_PREFERENCE_PREFIX}:${apiBase}:${userId}`;
}

export function getStoredWorkspaceProjectId(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const storageKey = getWorkspaceProjectPreferenceKey();
  if (!storageKey) {
    return "";
  }

  return window.localStorage.getItem(storageKey)?.trim() || "";
}

export function setStoredWorkspaceProjectId(projectId: string): void {
  if (typeof window === "undefined") {
    return;
  }

  const storageKey = getWorkspaceProjectPreferenceKey();
  const normalizedProjectId = projectId.trim();
  if (!storageKey) {
    return;
  }

  if (!normalizedProjectId) {
    window.localStorage.removeItem(storageKey);
    return;
  }

  window.localStorage.setItem(storageKey, normalizedProjectId);
}

export function clearStoredWorkspaceProjectId(): void {
  if (typeof window === "undefined") {
    return;
  }

  const storageKey = getWorkspaceProjectPreferenceKey();
  if (!storageKey) {
    return;
  }

  window.localStorage.removeItem(storageKey);
}
