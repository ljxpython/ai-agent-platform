"use client";

import { BaseChatTemplate } from "@/components/chat-template/base-chat-template";

const DEFAULT_PLATFORM_API_URL =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:2024";

export default function SqlAgentPage() {
  return (
    <BaseChatTemplate
      target={{
        targetType: "graph",
        graphId: "sql_agent",
        apiUrl: DEFAULT_PLATFORM_API_URL,
      }}
      display={{
        title: "SQL Agent",
        description:
          "Open a dedicated SQL Agent chat with the `sql_agent` graph pre-bound.",
      }}
      features={{
        allowAssistantSwitch: false,
        allowApiUrlEdit: false,
        allowRunOptions: true,
        showHistory: true,
        showArtifacts: true,
        showContextBar: true,
      }}
    />
  );
}
