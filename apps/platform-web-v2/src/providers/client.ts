import { Client } from "@langchain/langgraph-sdk";

export function createClient(
  apiUrl: string,
  apiKey: string | undefined,
  defaultHeaders?: Record<string, string>,
) {
  return new Client({
    apiKey,
    apiUrl,
    defaultHeaders,
  });
}
