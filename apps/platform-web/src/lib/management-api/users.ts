import { createManagementApiClient } from "./client";


export type ManagementUser = {
  id: string;
  username: string;
  status: string;
  is_super_admin: boolean;
  email?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};


type UserListResponse = {
  items: ManagementUser[];
  total: number;
};

export type ManagementUserProject = {
  project_id: string;
  project_name: string;
  project_description: string;
  project_status: string;
  role: "admin" | "editor" | "executor";
  joined_at: string;
};

type UserProjectListResponse = {
  items: ManagementUserProject[];
  total: number;
};


export async function listUsersPage(options?: { limit?: number; offset?: number; query?: string; status?: string; excludeUserIds?: string[] }): Promise<UserListResponse> {
  const client = createManagementApiClient();
  if (!client) {
    return { items: [], total: 0 };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 100));
  params.set("offset", String(options?.offset ?? 0));
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }
  if (options?.status?.trim()) {
    params.set("status", options.status.trim());
  }
  if (Array.isArray(options?.excludeUserIds) && options.excludeUserIds.length > 0) {
    const encoded = options.excludeUserIds.map((item) => item.trim()).filter(Boolean);
    if (encoded.length > 0) {
      params.set("exclude_user_ids", encoded.join(","));
    }
  }
  return client.get<UserListResponse>(`/_management/users?${params.toString()}`);
}


export async function listUsers(options?: { limit?: number; offset?: number; query?: string; status?: string }): Promise<ManagementUser[]> {
  const payload = await listUsersPage(options);
  return payload.items;
}

export async function getUser(userId: string): Promise<ManagementUser> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.get<ManagementUser>(`/_management/users/${userId}`);
}

export async function getMe(): Promise<ManagementUser> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.get<ManagementUser>("/_management/users/me");
}

export async function updateMe(payload: { username?: string; email?: string }): Promise<ManagementUser> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.patch<ManagementUser>("/_management/users/me", payload);
}

export async function listUserProjects(userId: string): Promise<UserProjectListResponse> {
  const client = createManagementApiClient();
  if (!client) {
    return { items: [], total: 0 };
  }
  return client.get<UserProjectListResponse>(`/_management/users/${userId}/projects`);
}


export async function createUser(payload: {
  username: string;
  password: string;
  is_super_admin?: boolean;
}): Promise<ManagementUser> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.post<ManagementUser>("/_management/users", payload);
}


export async function updateUser(
  userId: string,
  payload: {
    username?: string;
    password?: string;
    status?: "active" | "disabled";
    is_super_admin?: boolean;
  },
): Promise<ManagementUser> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.patch<ManagementUser>(`/_management/users/${userId}`, payload);
}
