import { createManagementApiClient } from "./client";

export type RuntimeModelItem = {
  id: string;
  runtime_id: string;
  model_id: string;
  display_name: string;
  is_default: boolean;
  sync_status: string;
  last_seen_at: string | null;
  last_synced_at: string | null;
};

export type RuntimeModelsResponse = {
  count: number;
  models: RuntimeModelItem[];
  last_synced_at: string | null;
};

export type RuntimeToolItem = {
  id: string;
  runtime_id: string;
  tool_key: string;
  name: string;
  source: string;
  description: string;
  sync_status: string;
  last_seen_at: string | null;
  last_synced_at: string | null;
};

export type RuntimeToolsResponse = {
  count: number;
  tools: RuntimeToolItem[];
  last_synced_at: string | null;
};

export type RuntimeRefreshResponse = {
  ok: boolean;
  count: number;
  last_synced_at: string | null;
};

export async function listRuntimeModels(): Promise<RuntimeModelsResponse> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.get<RuntimeModelsResponse>("/_management/runtime/models");
}

export async function refreshRuntimeModels(): Promise<RuntimeRefreshResponse> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.post<RuntimeRefreshResponse>(
    "/_management/catalog/models/refresh",
    {},
  );
}

export async function listRuntimeTools(): Promise<RuntimeToolsResponse> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.get<RuntimeToolsResponse>("/_management/runtime/tools");
}

export async function refreshRuntimeTools(): Promise<RuntimeRefreshResponse> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.post<RuntimeRefreshResponse>(
    "/_management/catalog/tools/refresh",
    {},
  );
}
