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
  config?: Record<string, unknown>;
  context?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type AssistantListResponse = {
  items: ManagementAssistant[];
  total: number;
};

export type AssistantParameterSchemaProperty = {
  type?: string;
  required?: boolean;
};

export type AssistantParameterSchemaSection = {
  key?: string;
  title?: string;
  type?: string;
  properties?: Record<string, AssistantParameterSchemaProperty>;
};

export type AssistantParameterSchema = {
  graph_id?: string;
  schema_version?: string;
  sections?: AssistantParameterSchemaSection[];
};

export async function listAssistantsPage(
  projectId: string,
  options?: {
    limit?: number;
    offset?: number;
    query?: string;
    graph_id?: string;
  },
): Promise<AssistantListResponse> {
  const client = createManagementApiClient({
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

  return client.get<AssistantListResponse>(
    `/_management/projects/${projectId}/assistants?${params.toString()}`,
  );
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
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }

  return client.post<ManagementAssistant>(
    `/_management/projects/${projectId}/assistants`,
    payload,
  );
}

export async function getAssistant(
  assistantId: string,
  projectId?: string,
): Promise<ManagementAssistant> {
  const client = createManagementApiClient({
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.get<ManagementAssistant>(
    `/_management/assistants/${assistantId}`,
  );
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
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.patch<ManagementAssistant>(
    `/_management/assistants/${assistantId}`,
    payload,
  );
}

export async function resyncAssistant(
  assistantId: string,
  projectId?: string,
): Promise<ManagementAssistant> {
  const client = createManagementApiClient({
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.post<ManagementAssistant>(
    `/_management/assistants/${assistantId}/resync`,
    {},
  );
}

export async function getAssistantParameterSchema(
  graphId: string,
  projectId?: string,
): Promise<AssistantParameterSchema> {
  const client = createManagementApiClient({
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.get<AssistantParameterSchema>(
    `/_management/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`,
  );
}
