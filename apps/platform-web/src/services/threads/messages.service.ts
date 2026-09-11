import { platformHttpClient } from "@/services/http/client";

export type MessageReceipt = {
  message_id: string;
  thread_id: string;
  target_run_id: string;
  sequence: number;
  status: "queued" | "claimed" | "consumed" | "rejected" | "not_consumed";
  reason?: string | null;
  /** Only the authenticated sender's original content; never internal authorization. */
  content?: unknown;
};

export async function listThreadMessages(
  projectId: string,
  threadId: string,
  signal?: AbortSignal,
) {
  const { data } = await platformHttpClient.get<{ messages: MessageReceipt[] }>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/messages`,
    { headers: { "x-project-id": projectId }, signal },
  );
  return data.messages;
}

export async function enqueueThreadMessage(
  projectId: string,
  threadId: string,
  payload: {
    client_message_id: string;
    target_run_id: string;
    content: unknown;
  },
  idempotencyKey: string,
): Promise<MessageReceipt> {
  const { data } = await platformHttpClient.post<MessageReceipt>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/messages`,
    payload,
    {
      headers: { "x-project-id": projectId, "Idempotency-Key": idempotencyKey },
    },
  );
  return data;
}
