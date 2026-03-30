"use client";

import { ArtifactProvider } from "@/components/thread/artifact";
import { Thread } from "@/components/thread";
import { Toaster } from "@/components/ui/sonner";
import { StreamProvider } from "@/providers/Stream";
import { ThreadProvider } from "@/providers/Thread";
import React, { type ReactNode } from "react";

export type ChatTargetType = "assistant" | "graph";

export type ChatTargetConfig = {
  targetType: ChatTargetType;
  assistantId?: string;
  graphId?: string;
  apiUrl?: string;
  projectId?: string;
};

export type BaseChatTemplateDisplayConfig = {
  title: string;
  description?: string;
  emptyTitle?: string;
  emptyDescription?: string;
};

export type BaseChatTemplateFeatureFlags = {
  allowAssistantSwitch?: boolean;
  allowApiUrlEdit?: boolean;
  allowRunOptions?: boolean;
  showHistory?: boolean;
  showArtifacts?: boolean;
  showContextBar?: boolean;
};

export type BaseChatTemplateSlots = {
  headerSlot?: ReactNode;
  contextSlot?: ReactNode;
  emptyStateSlot?: ReactNode;
  rightPanelSlot?: ReactNode;
};

export type BaseChatTemplateProps = {
  target: ChatTargetConfig;
  display: BaseChatTemplateDisplayConfig;
  features?: BaseChatTemplateFeatureFlags;
  slots?: BaseChatTemplateSlots;
};

function resolveTargetId(target: ChatTargetConfig): string {
  if (target.targetType === "graph") {
    return target.graphId?.trim() || target.assistantId?.trim() || "";
  }
  return target.assistantId?.trim() || "";
}

export function BaseChatTemplate({
  target,
  display,
  features,
  slots,
}: BaseChatTemplateProps): React.ReactNode {
  const resolvedTargetId = resolveTargetId(target);

  return (
    <React.Suspense fallback={<div>Loading chat...</div>}>
      <Toaster />
      <ThreadProvider
        initialApiUrl={target.apiUrl}
        initialAssistantId={resolvedTargetId}
        initialGraphId={target.graphId}
        initialTargetType={target.targetType}
      >
        <StreamProvider
          initialApiUrl={target.apiUrl}
          initialAssistantId={resolvedTargetId}
          initialGraphId={target.graphId}
          initialTargetType={target.targetType}
          title={display.title}
          description={display.description}
          allowAssistantSwitch={features?.allowAssistantSwitch ?? false}
          allowApiUrlEdit={features?.allowApiUrlEdit ?? false}
        >
          <ArtifactProvider>
            <Thread
              title={display.title}
              description={display.description}
              emptyTitle={display.emptyTitle}
              emptyDescription={display.emptyDescription}
              initialAssistantId={resolvedTargetId}
              initialGraphId={target.graphId}
              initialTargetType={target.targetType}
              features={features}
              slots={slots}
            />
          </ArtifactProvider>
        </StreamProvider>
      </ThreadProvider>
    </React.Suspense>
  );
}
