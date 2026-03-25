import { createManagementApiClient } from "./client";
import type { ArtifactRecord } from "@/lib/types/artifacts";
import { getStoredOrConfiguredPlatformApiUrl } from "@/lib/platform-api-url";

type ArtifactListResponse = {
  items: ArtifactRecord[];
  total: number;
  limit: number;
  offset: number;
};

export async function getArtifact(
  projectId: string,
  artifactId: string,
): Promise<ArtifactRecord> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<ArtifactRecord>(`/_management/artifacts/${encodeURIComponent(artifactId)}`);
}

export async function listThreadArtifacts(
  projectId: string,
  threadId: string,
): Promise<ArtifactRecord[]> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    return [];
  }
  const response = await client.get<ArtifactListResponse>(
    `/_management/threads/${encodeURIComponent(threadId)}/artifacts`,
  );
  return response.items;
}

export function buildArtifactDownloadUrl(downloadUrl: string): string {
  const baseUrl = getStoredOrConfiguredPlatformApiUrl();
  return `${String(baseUrl).replace(/\/+$/, "")}${downloadUrl}`;
}
