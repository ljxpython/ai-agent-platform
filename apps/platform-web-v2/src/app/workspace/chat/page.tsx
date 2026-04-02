"use client";

import { useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";

import { BaseChatTemplate } from "@/components/chat-template/base-chat-template";
import { ChatEntryGuide } from "@/components/platform/chat-entry-guide";
import { PageStateLoading } from "@/components/platform/page-state";
import {
  parseChatTargetSearchParams,
  readRecentChatTarget,
  writeRecentChatTarget,
} from "@/lib/chat-target-preference";
import { getConfiguredPlatformApiUrl } from "@/lib/platform-api-url";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

export default function WorkspaceChatPage() {
  const searchParams = useSearchParams();
  const { projectId, loading } = useWorkspaceContext();

  const explicitTarget = useMemo(
    () => parseChatTargetSearchParams(searchParams),
    [searchParams],
  );

  const recentTarget = useMemo(() => {
    if (loading || explicitTarget || !projectId || typeof window === "undefined") {
      return null;
    }
    return readRecentChatTarget(projectId);
  }, [explicitTarget, loading, projectId]);

  useEffect(() => {
    if (explicitTarget && projectId) {
      writeRecentChatTarget(projectId, explicitTarget);
    }
  }, [explicitTarget, projectId]);

  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center">
        <div className="w-full max-w-xl">
          <PageStateLoading message="Loading chat workspace..." />
        </div>
      </div>
    );
  }

  const target = explicitTarget || recentTarget;

  if (!target) {
    return <ChatEntryGuide projectId={projectId} />;
  }

  return (
    <BaseChatTemplate
      target={{
        targetType: target.targetType,
        assistantId: target.assistantId,
        graphId: target.graphId,
        apiUrl: getConfiguredPlatformApiUrl(),
        projectId,
      }}
      display={{
        title: "Agent Chat",
        description:
          "Open a project-scoped chat bound to your recent assistant or graph target.",
        emptyTitle: "Agent Chat",
        emptyDescription:
          "Chat reuses your last selected target. If you need a different target, switch from Assistants or Graphs first.",
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
