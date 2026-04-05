import { createManagementApiClient } from "./client";

export async function login(payload: {
  username: string;
  password: string;
}): Promise<{
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

export async function changePassword(payload: {
  oldPassword: string;
  newPassword: string;
}): Promise<{ ok: boolean }> {
  const client = createManagementApiClient();
  if (!client) {
    throw new Error("management_api_unavailable");
  }

  return client.post<{ ok: boolean }>("/_management/auth/change-password", {
    old_password: payload.oldPassword,
    new_password: payload.newPassword,
  });
}
