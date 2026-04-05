import { createManagementApiClient } from "./client";

export type ManagementProjectMember = {
  user_id: string;
  username: string;
  role: "admin" | "editor" | "executor";
};

type MemberListResponse = {
  items: ManagementProjectMember[];
};

export async function listMembers(
  projectId: string,
  options?: { query?: string },
): Promise<ManagementProjectMember[]> {
  const client = createManagementApiClient();
  if (!client || !projectId) {
    return [];
  }

  const params = new URLSearchParams();
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }

  const path =
    params.size > 0
      ? `/_management/projects/${projectId}/members?${params.toString()}`
      : `/_management/projects/${projectId}/members`;
  const payload = await client.get<MemberListResponse>(path);
  return payload.items;
}

export async function upsertMember(payload: {
  projectId: string;
  userId: string;
  role: "admin" | "editor" | "executor";
}): Promise<ManagementProjectMember> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.post<ManagementProjectMember>(
    `/_management/projects/${payload.projectId}/members`,
    {
      user_id: payload.userId,
      role: payload.role,
    },
  );
}

export async function deleteMember(
  projectId: string,
  userId: string,
): Promise<{ ok: boolean }> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.del<{ ok: boolean }>(
    `/_management/projects/${projectId}/members/${userId}`,
  );
}
