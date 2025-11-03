import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { ToolCalls } from "./tool-calls-new";
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment } from "react/jsx-runtime";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsBoolean } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { useArtifact } from "../artifact";
// TODO  MC80OmFIVnBZMlhtblk3a3ZiUG1yS002WTBKdVV3PT06OTZmMGViNGI=

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

  return toolCallContents
    .map((tc) => {
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
        type: "tool_call" as const,
      };
    })
    .filter((tc) => tc.name && tc.name.trim() !== ""); // Filter out empty names
}
// FIXME  MS80OmFIVnBZMlhtblk3a3ZiUG1yS002WTBKdVV3PT06OTZmMGViNGI=

interface InterruptProps {
  interruptValue?: unknown;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
}
// @ts-expect-error  Mi80OmFIVnBZMlhtblk3a3ZiUG1yS002WTBKdVV3PT06OTZmMGViNGI=

function Interrupt({
  interruptValue,
  isLastMessage,
  hasNoAIOrToolMessages,
}: InterruptProps) {
  return (
    <>
      {isAgentInboxInterruptSchema(interruptValue) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interruptValue} />
        )}
      {interruptValue &&
      !isAgentInboxInterruptSchema(interruptValue) &&
      (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={interruptValue} />
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
    message.tool_calls?.some(
      (tc) => tc.args && Object.keys(tc.args).length > 0,
    );
  const hasAnthropicToolCalls = !!anthropicStreamedToolCalls?.length;
  const isToolResult = message?.type === "tool";

  if (isToolResult) {
    return null; // Hide individual tool results since they're now combined with tool calls
  }

  return (
    <div className="group mr-auto w-full">
      <div className="flex flex-col gap-2">
        {!isToolResult && (
          <>
            {contentString.length > 0 && (
              <div className="py-1">
                <MarkdownText>{contentString}</MarkdownText>
              </div>
            )}

            {!hideToolCalls && (
              <>
                {(hasToolCalls && toolCallsHaveContents && (
                  <div className="group/tool">
                    <ToolCalls
                      toolCalls={message.tool_calls}
                      toolResults={thread.messages.filter(
                        (m): m is import("@langchain/langgraph-sdk").ToolMessage =>
                          m.type === "tool" &&
                          !!message.tool_calls?.some(tc => tc.id === (m as any).tool_call_id)
                      )}
                    />
                  </div>
                )) ||
                  (hasAnthropicToolCalls && (
                    <div className="group/tool">
                      <ToolCalls
                        toolCalls={anthropicStreamedToolCalls}
                        toolResults={thread.messages.filter(
                          (m): m is import("@langchain/langgraph-sdk").ToolMessage =>
                            m.type === "tool" &&
                            anthropicStreamedToolCalls?.some(tc => tc.id === (m as any).tool_call_id)
                        )}
                      />
                    </div>
                  )) ||
                  (hasToolCalls && (
                    <div className="group/tool">
                      <ToolCalls
                        toolCalls={message.tool_calls}
                        toolResults={thread.messages.filter(
                          (m): m is import("@langchain/langgraph-sdk").ToolMessage =>
                            m.type === "tool" &&
                            !!message.tool_calls?.some(tc => tc.id === (m as any).tool_call_id)
                        )}
                      />
                    </div>
                  ))}
              </>
            )}

            {message && (
              <CustomComponent
                message={message}
                thread={thread}
              />
            )}
            <Interrupt
              interruptValue={threadInterrupt?.value}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
            <div
              className={cn(
                "mr-auto flex items-center gap-2 transition-opacity",
                "opacity-100 md:opacity-100",
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
// FIXME  My80OmFIVnBZMlhtblk3a3ZiUG1yS002WTBKdVV3PT06OTZmMGViNGI=
