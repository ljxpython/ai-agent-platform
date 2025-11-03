import { Client } from "@langchain/langgraph-sdk";
// NOTE  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002T1VrMlNBPT06ZjQwYTg2MzE=

export function createClient(apiUrl: string, apiKey: string | undefined) {
  return new Client({
    apiKey,
    apiUrl,
  });
}
