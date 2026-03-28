import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message, ToolMessage } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { ToolCalls, ToolResult } from "./tool-calls";
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment } from "react/jsx-runtime";
import { useMemo, useState } from "react";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsBoolean } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { useArtifact } from "../artifact";
import { ChevronDown, ChevronUp } from "lucide-react";

type SubAgentCard = {
  id: string;
  name: string;
  status: "pending" | "completed";
  input: string;
  output?: string;
};

function normalizeToolCallInput(args: unknown): string {
  if (args == null) {
    return "";
  }
  if (typeof args === "string") {
    return args;
  }
  if (typeof args === "object") {
    const argsRecord = args as Record<string, unknown>;
    const task =
      typeof argsRecord.task === "string"
        ? argsRecord.task
        : typeof argsRecord.description === "string"
          ? argsRecord.description
          : "";
    if (task.trim()) {
      return task;
    }
    return JSON.stringify(argsRecord, null, 2);
  }
  return String(args);
}

function getSubAgentName(args: unknown): string {
  if (!args || typeof args !== "object") {
    return "sub-agent";
  }
  const argsRecord = args as Record<string, unknown>;
  const candidate = argsRecord.subagent_type;
  if (typeof candidate === "string" && candidate.trim()) {
    return candidate.trim();
  }
  return "sub-agent";
}

function extractSubAgentCards(
  message: Message | undefined,
  threadMessages: Message[],
): SubAgentCard[] {
  if (!message || message.type !== "ai" || !Array.isArray(message.tool_calls)) {
    return [];
  }

  const toolMessages = threadMessages.filter((item) => item.type === "tool");

  return message.tool_calls
    .filter((toolCall) => toolCall?.name === "task")
    .map((toolCall, index) => {
      const id =
        typeof toolCall.id === "string" && toolCall.id.trim()
          ? toolCall.id
          : `task-${message.id ?? "message"}-${index + 1}`;
      const matchingResult = toolMessages.find(
        (toolMessage) => toolMessage.tool_call_id === toolCall.id,
      );
      const output = matchingResult ? getContentString(matchingResult.content) : "";
      return {
        id,
        name: getSubAgentName(toolCall.args),
        status: matchingResult ? "completed" : "pending",
        input: normalizeToolCallInput(toolCall.args),
        output: output || undefined,
      } satisfies SubAgentCard;
    });
}

function SubAgentCards({ items }: { items: SubAgentCard[] }) {
  const [openMap, setOpenMap] = useState<Record<string, boolean>>({});

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="mx-auto grid max-w-3xl gap-2">
      {items.map((item) => {
        const isOpen = openMap[item.id] ?? true;
        return (
          <div key={item.id} className="overflow-hidden rounded-lg border border-border bg-card">
            <button
              type="button"
              className="flex w-full items-center justify-between px-3 py-2 text-left"
              onClick={() =>
                setOpenMap((prev) => ({
                  ...prev,
                  [item.id]: !(prev[item.id] ?? true),
                }))
              }
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "inline-block size-2 rounded-full",
                    item.status === "completed" ? "bg-emerald-600" : "bg-amber-500",
                  )}
                />
                <span className="text-sm font-medium text-foreground">{item.name}</span>
                <span className="text-xs text-muted-foreground">
                  {item.status === "completed" ? "completed" : "running"}
                </span>
              </div>
              {isOpen ? (
                <ChevronUp className="size-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="size-4 text-muted-foreground" />
              )}
            </button>

            {isOpen ? (
              <div className="space-y-2 border-t border-border/80 px-3 py-2">
                <div>
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Input</p>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted/40 px-2 py-1.5 text-xs text-foreground">
                    {item.input || "<empty>"}
                  </pre>
                </div>
                {item.output ? (
                  <div>
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Output</p>
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted/40 px-2 py-1.5 text-xs text-foreground">
                      {item.output}
                    </pre>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function CustomComponent({
  message,
  thread,
}: {
  message: Message;
  thread: ReturnType<typeof useStreamContext>;
}) {
  const artifact = useArtifact();
  const { values } = useStreamContext();
  const customComponents = values.ui?.filter(
    (ui) => ui.metadata?.message_id === message.id,
  );

  if (!customComponents?.length) return null;
  return (
    <Fragment key={message.id}>
      {customComponents.map((customComponent) => (
        <LoadExternalComponent
          key={customComponent.id}
          stream={thread}
          message={customComponent}
          meta={{ ui: customComponent, artifact }}
        />
      ))}
    </Fragment>
  );
}

function parseAnthropicStreamedToolCalls(
  content: MessageContentComplex[],
): AIMessage["tool_calls"] {
  const toolCallContents = content.filter((c) => c.type === "tool_use" && c.id);
  return toolCallContents.map((tc) => {
    const toolCall = tc as Record<string, any>;
    let json: Record<string, any> = {};
    if (toolCall?.input) {
      try {
        json = parsePartialJson(toolCall.input) ?? {};
      } catch {
        // Pass
      }
    }
    return {
      name: toolCall.name ?? "",
      id: toolCall.id ?? "",
      args: json,
      type: "tool_call",
    };
  });
}

interface InterruptProps {
  interrupt?: unknown;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
}

function Interrupt({
  interrupt,
  isLastMessage,
  hasNoAIOrToolMessages,
}: InterruptProps) {
  const fallbackValue = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown } | undefined)?.value ??
        interrupt) as Record<string, any>);
  return (
    <>
      {isAgentInboxInterruptSchema(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interrupt} />
        )}
      {interrupt &&
        !isAgentInboxInterruptSchema(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={fallbackValue} />
      ) : null}
    </>
  );
}

export function AssistantMessage({
  message,
  isLoading,
  handleRegenerate,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
}) {
  const content = message?.content ?? [];
  const contentString = getContentString(content);
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );

  const thread = useStreamContext();
  const isLastMessage =
    thread.messages[thread.messages.length - 1].id === message?.id;
  const hasNoAIOrToolMessages = !thread.messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const meta = message ? thread.getMessagesMetadata(message) : undefined;
  const threadInterrupt = thread.interrupt;
  const parentCheckpoint = meta?.firstSeenState?.parent_checkpoint;
  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content)
    : undefined;
  const hasToolCalls =
    message &&
    "tool_calls" in message &&
    message.tool_calls &&
    message.tool_calls.length > 0;
  const toolCallsHaveContents =
    hasToolCalls &&
    (message.tool_calls?.some(
      (tc) => tc.args && Object.keys(tc.args).length > 0,
    ) ?? false);
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";
  const toolResultsByCallId = useMemo(() => {
    const result: Record<string, ToolMessage> = {};
    for (const item of thread.messages) {
      if (
        item.type === "tool" &&
        typeof item.tool_call_id === "string" &&
        item.tool_call_id.trim()
      ) {
        result[item.tool_call_id] = item;
      }
    }
    return result;
  }, [thread.messages]);
  const linkedToolCallIds = useMemo(() => {
    const ids = new Set<string>();
    for (const item of thread.messages) {
      if (item.type !== "ai" || !Array.isArray(item.tool_calls)) {
        continue;
      }
      for (const toolCall of item.tool_calls) {
        if (typeof toolCall?.id === "string" && toolCall.id.trim()) {
          ids.add(toolCall.id);
        }
      }
    }
    return ids;
  }, [thread.messages]);
  const shouldHideStandaloneToolResult = Boolean(
    isToolResult &&
      typeof message?.tool_call_id === "string" &&
      linkedToolCallIds.has(message.tool_call_id),
  );
  const subAgentCards = extractSubAgentCards(message, thread.messages);

  if (isToolResult && hideToolCalls) {
    return null;
  }

  if (shouldHideStandaloneToolResult) {
    const shouldShowInterrupt =
      Boolean(threadInterrupt) && (isLastMessage || hasNoAIOrToolMessages);
    if (!shouldShowInterrupt) {
      return null;
    }
    return (
      <div className="group mr-auto flex w-full items-start gap-2">
        <div className="flex w-full flex-col gap-2">
          <Interrupt
            interrupt={threadInterrupt}
            isLastMessage={isLastMessage}
            hasNoAIOrToolMessages={hasNoAIOrToolMessages}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="group mr-auto flex w-full items-start gap-2">
      <div className="flex w-full flex-col gap-2">
        {isToolResult ? (
          <>
            <ToolResult message={message} />
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
          </>
        ) : (
          <>
            {contentString.length > 0 && (
              <div className="py-1">
                <MarkdownText>{contentString}</MarkdownText>
              </div>
            )}
            {!hideToolCalls && (
              <>
                {(hasToolCalls && toolCallsHaveContents && (
                  <ToolCalls
                    toolCalls={message.tool_calls}
                    toolResultsByCallId={toolResultsByCallId}
                  />
                )) ||
                  (hasAnthropicToolCalls && (
                    <ToolCalls
                      toolCalls={anthropicStreamedToolCalls}
                      toolResultsByCallId={toolResultsByCallId}
                    />
                  )) ||
                  (hasToolCalls && (
                    <ToolCalls
                      toolCalls={message.tool_calls}
                      toolResultsByCallId={toolResultsByCallId}
                    />
                  ))}
              </>
            )}
            {!hideToolCalls && <SubAgentCards items={subAgentCards} />}
            {message && (
              <CustomComponent
                message={message}
                thread={thread}
              />
            )}
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
            <div
              className={cn(
                "ml-auto flex items-center gap-2 transition-opacity",
                "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
              )}
            >
              <BranchSwitcher
                branch={meta?.branch}
                branchOptions={meta?.branchOptions}
                onSelect={(branch) => thread.setBranch(branch)}
                isLoading={isLoading}
              />
              <CommandBar
                content={contentString}
                isLoading={isLoading}
                isAiMessage={true}
                handleRegenerate={() => handleRegenerate(parentCheckpoint)}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function AssistantMessageLoading() {
  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-muted flex h-8 items-center gap-1 rounded-2xl px-4 py-2">
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_0.5s_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_1s_infinite] rounded-full"></div>
      </div>
    </div>
  );
}
