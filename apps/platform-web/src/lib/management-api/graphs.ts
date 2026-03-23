import { createManagementApiClient } from "./client";

export type ManagementGraph = {
  id: string;
  runtime_id: string;
  graph_id: string;
  display_name: string;
  description?: string;
  source_type: string;
  sync_status: string;
  last_synced_at: string | null;
};

type GraphListResponse = {
  items: ManagementGraph[];
  total: number;
  last_synced_at?: string | null;
};

export async function listGraphsPage(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string },
): Promise<GraphListResponse> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    return { items: [], total: 0, last_synced_at: null };
  }

  const payload = await client.get<GraphListResponse>("/_management/catalog/graphs");
  const normalizedQuery = options?.query?.trim().toLowerCase() || "";
  const filtered = normalizedQuery
    ? payload.items.filter(
        (item) =>
          item.graph_id.toLowerCase().includes(normalizedQuery) ||
          item.display_name.toLowerCase().includes(normalizedQuery) ||
          (item.description || "").toLowerCase().includes(normalizedQuery),
      )
    : payload.items;
  const limit = options?.limit ?? 20;
  const offset = options?.offset ?? 0;
  return {
    items: filtered.slice(offset, offset + limit),
    total: filtered.length,
    last_synced_at: payload.last_synced_at ?? null,
  };
}


export async function refreshGraphsCatalog(
  projectId?: string,
): Promise<{ ok: boolean; count: number; last_synced_at: string | null }> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.post("/_management/catalog/graphs/refresh", {});
}
