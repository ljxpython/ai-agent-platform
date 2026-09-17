import { platformHttpClient } from "@/services/http/client";
import type { AccessPolicy } from "./session.service";

export interface UpdateAccessPolicyResponse {
  thread_id: string;
  access_policy: AccessPolicy;
}

export async function updateThreadAccessPolicy(
  projectId: string,
  threadId: string,
  accessPolicy: AccessPolicy,
): Promise<UpdateAccessPolicyResponse> {
  const { data } = await platformHttpClient.patch<UpdateAccessPolicyResponse>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/access-policy`,
    { access_policy: accessPolicy },
    {
      headers: {
        "x-project-id": projectId,
      },
    },
  );
  return data;
}
