import { createManagementApiClient } from "./client";

export type ManagementAuditRow = {
  id: string;
  request_id: string;
  action: string | null;
  target_type: string | null;
  target_id: string | null;
  method: string;
  path: string;
  status_code: number;
  created_at: string;
  user_id: string | null;
};

type AuditListResponse = {
  items: ManagementAuditRow[];
  total: number;
};

export async function listAudit(
  projectId: string | null,
  options?: {
    limit?: number;
    offset?: number;
    action?: string;
    targetType?: string;
    targetId?: string;
    method?: string;
    statusCode?: number | null;
  },
): Promise<AuditListResponse> {
  const client = createManagementApiClient();
  if (!client) {
    return { items: [], total: 0 };
  }

  const params = new URLSearchParams();
  if (projectId && projectId.trim()) {
    params.set("project_id", projectId);
  }
  params.set("limit", String(options?.limit ?? 50));
  params.set("offset", String(options?.offset ?? 0));
  if (options?.action?.trim()) {
    params.set("action", options.action.trim());
  }
  if (options?.targetType?.trim()) {
    params.set("target_type", options.targetType.trim());
  }
  if (options?.targetId?.trim()) {
    params.set("target_id", options.targetId.trim());
  }
  if (options?.method?.trim()) {
    params.set("method", options.method.trim().toUpperCase());
  }
  if (typeof options?.statusCode === "number" && options.statusCode > 0) {
    params.set("status_code", String(options.statusCode));
  }

  return client.get<AuditListResponse>(
    `/_management/audit?${params.toString()}`,
  );
}
