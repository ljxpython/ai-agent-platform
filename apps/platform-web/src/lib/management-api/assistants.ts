import { createManagementApiClient } from "./client";

export type ManagementAssistant = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  graph_id: string;
  langgraph_assistant_id: string;
  runtime_base_url: string;
  sync_status: string;
  last_sync_error?: string | null;
  last_synced_at?: string | null;
  status: "active" | "disabled";
  config: Record<string, unknown>;
  context: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type AssistantListResponse = {
  items: ManagementAssistant[];
  total: number;
};

export async function listAssistantsPage(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string; graph_id?: string },
): Promise<AssistantListResponse> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    return { items: [], total: 0 };
  }

  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 20));
  params.set("offset", String(options?.offset ?? 0));
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }
  if (options?.graph_id?.trim()) {
    params.set("graph_id", options.graph_id.trim());
  }

  return client.get<AssistantListResponse>(`/_management/projects/${projectId}/assistants?${params.toString()}`);
}

export async function createAssistant(
  projectId: string,
  payload: {
    graph_id: string;
    name: string;
    description?: string;
    assistant_id?: string;
    config?: Record<string, unknown>;
    context?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  },
): Promise<ManagementAssistant> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.post<ManagementAssistant>(`/_management/projects/${projectId}/assistants`, payload);
}

export async function getAssistant(assistantId: string, projectId?: string): Promise<ManagementAssistant> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.get<ManagementAssistant>(`/_management/assistants/${assistantId}`);
}

export async function updateAssistant(
  assistantId: string,
  payload: {
    graph_id?: string;
    name?: string;
    description?: string;
    status?: "active" | "disabled";
    config?: Record<string, unknown>;
    context?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  },
  projectId?: string,
): Promise<ManagementAssistant> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.patch<ManagementAssistant>(`/_management/assistants/${assistantId}`, payload);
}

export async function deleteAssistant(
  assistantId: string,
  options?: { deleteRuntime?: boolean; deleteThreads?: boolean; projectId?: string },
): Promise<{ ok: boolean }> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: options?.projectId ? { "x-project-id": options.projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  const params = new URLSearchParams();
  if (options?.deleteRuntime) {
    params.set("delete_runtime", "true");
  }
  if (options?.deleteThreads) {
    params.set("delete_threads", "true");
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return client.del<{ ok: boolean }>(`/_management/assistants/${assistantId}${suffix}`);
}


export async function resyncAssistant(assistantId: string, projectId?: string): Promise<ManagementAssistant> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.post<ManagementAssistant>(`/_management/assistants/${assistantId}/resync`, {});
}

export async function getAssistantParameterSchema(
  graphId: string,
  projectId?: string,
): Promise<Record<string, unknown>> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.get<Record<string, unknown>>(`/_management/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`);
}
