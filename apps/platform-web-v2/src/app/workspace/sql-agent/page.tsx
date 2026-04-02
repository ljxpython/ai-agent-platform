"use client";

import { BaseChatTemplate } from "@/components/chat-template/base-chat-template";
import { getConfiguredPlatformApiUrl } from "@/lib/platform-api-url";

export default function SqlAgentPage() {
  const defaultPlatformApiUrl = getConfiguredPlatformApiUrl();

  return (
    <BaseChatTemplate
      target={{
        targetType: "graph",
        graphId: "sql_agent",
        apiUrl: defaultPlatformApiUrl,
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
