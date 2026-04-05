import { createManagementApiClient } from "./client";

export type ManagementProject = {
  id: string;
  name: string;
  description: string;
  status: string;
};

type ProjectListResponse = {
  items: ManagementProject[];
  total: number;
};

export async function listProjectsPage(options?: {
  limit?: number;
  offset?: number;
  query?: string;
}): Promise<ProjectListResponse> {
  const client = createManagementApiClient();
  if (!client) {
    return { items: [], total: 0 };
  }

  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 20));
  params.set("offset", String(options?.offset ?? 0));
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }

  return client.get<ProjectListResponse>(
    `/_management/projects?${params.toString()}`,
  );
}

export async function listProjects(options?: {
  limit?: number;
  offset?: number;
  query?: string;
}): Promise<ManagementProject[]> {
  const payload = await listProjectsPage(options);
  return payload.items;
}

export async function createProject(payload: {
  name: string;
  description?: string;
}): Promise<ManagementProject> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.post<ManagementProject>("/_management/projects", payload);
}
