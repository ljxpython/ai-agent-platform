import { createManagementApiClient } from "./client";

export async function login(payload: { username: string; password: string }): Promise<{
  access_token: string;
  refresh_token: string;
  token_type: string;
}> {
  const client = createManagementApiClient({ requireAuth: false });
  if (!client) {
    throw new Error("management_api_unavailable");
  }
  return client.post("/_management/auth/login", payload);
}
