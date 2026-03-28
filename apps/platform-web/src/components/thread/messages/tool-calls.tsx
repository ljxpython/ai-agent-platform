import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, CircleCheckBigIcon, Loader2, StopCircle } from "lucide-react";
import { MarkdownText } from "../markdown-text";
import { cn } from "@/lib/utils";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeToolResultContent(content: ToolMessage["content"]): string {
  if (typeof content === "string") {
    return content;
  }
  try {
    return JSON.stringify(content, null, 2);
  } catch {
    return String(content);
  }
}

function normalizeToolArgs(args: unknown): Record<string, unknown> {
  if (isRecord(args)) {
    return args;
  }
  if (typeof args === "string") {
    try {
      const parsed = JSON.parse(args);
      if (isRecord(parsed)) {
        return parsed;
      }
    } catch {
      // ignore parse error
    }
    return { input: args };
  }
  return {};
}

function getStatusIcon(hasResult: boolean) {
  if (hasResult) {
    return <CircleCheckBigIcon className="size-4 text-emerald-500" />;
  }
  return <Loader2 className="size-4 animate-spin text-muted-foreground" />;
}

function ToolCallCard({
  toolCall,
  toolResult,
}: {
  toolCall: NonNullable<AIMessage["tool_calls"]>[number];
  toolResult?: ToolMessage;
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedArgs, setExpandedArgs] = useState<Record<string, boolean>>({});
  const args = useMemo(() => normalizeToolArgs(toolCall.args), [toolCall.args]);
  const hasArgs = Object.keys(args).length > 0;
  const resultContent = toolResult ? normalizeToolResultContent(toolResult.content) : "";
  const hasResult = resultContent.trim().length > 0;
  const hasContent = hasArgs || hasResult;

  return (
    <div className="w-full overflow-hidden rounded-lg border border-border/70 bg-card shadow-none outline-none">
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        disabled={!hasContent}
        className={cn(
          "flex w-full items-center justify-between gap-2 border-none px-3 py-2.5 text-left shadow-none outline-none transition-colors focus-visible:ring-0 focus-visible:ring-offset-0 disabled:cursor-default",
          hasContent ? "hover:bg-muted/45" : "",
          hasContent && isExpanded ? "bg-muted/45" : "bg-muted/35",
        )}
      >
        <div className="flex items-center gap-2">
          {getStatusIcon(hasResult)}
          <span className="text-[15px] font-medium tracking-[-0.4px] text-foreground">
            {toolCall.name || "Unknown Tool"}
          </span>
        </div>
        {hasContent ? (
          isExpanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )
        ) : null}
      </button>

      {isExpanded && hasContent ? (
        <div className="border-t border-border/70 bg-muted/20 px-4 pb-4 pt-3">
          {hasArgs ? (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Args
              </h4>
              <div className="space-y-2">
                {Object.entries(args).map(([key, value]) => {
                  const isArgOpen = expandedArgs[key] ?? false;
                  const valueString =
                    typeof value === "string" ? value : JSON.stringify(value, null, 2);
                  return (
                    <div
                      key={key}
                      className="rounded-md border border-border/70 bg-card/70"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedArgs((prev) => ({
                            ...prev,
                            [key]: !isArgOpen,
                          }))
                        }
                        className="flex w-full items-center justify-between bg-muted/35 p-2 text-left text-xs font-medium transition-colors hover:bg-muted/45"
                      >
                        <span className="font-mono">{key}</span>
                        {isArgOpen ? (
                          <ChevronUp className="size-3.5 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="size-3.5 text-muted-foreground" />
                        )}
                      </button>
                      {isArgOpen ? (
                        <div className="border-t border-border/70 bg-muted/25 p-2">
                          <pre className="m-0 overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs leading-6 text-foreground">
                            {valueString}
                          </pre>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {hasResult ? (
            <div className="mt-4">
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Result
              </h4>
              <div className="rounded-md border border-border/70 bg-card/70 p-2">
                <MarkdownText>{resultContent}</MarkdownText>
              </div>
            </div>
          ) : null}

          {toolCall.id ? (
            <div className="mt-3">
              <code className="rounded bg-muted/60 px-2 py-1 text-[11px] text-muted-foreground">
                {toolCall.id}
              </code>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function ToolCalls({
  toolCalls,
  toolResultsByCallId,
}: {
  toolCalls: AIMessage["tool_calls"];
  toolResultsByCallId?: Record<string, ToolMessage>;
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mt-4 flex w-full flex-col gap-2">
      {toolCalls.map((toolCall, index) => {
        if (toolCall?.name === "task") {
          return null;
        }
        const toolCallId =
          typeof toolCall?.id === "string" && toolCall.id.trim() ? toolCall.id : "";
        const toolResult = toolCallId ? toolResultsByCallId?.[toolCallId] : undefined;

        return (
          <ToolCallCard
            key={toolCallId || `${toolCall?.name || "tool"}-${index + 1}`}
            toolCall={toolCall}
            toolResult={toolResult}
          />
        );
      })}
    </div>
  );
}

export function ToolResult(_props: { message: ToolMessage }) {
  return (
    <div className="hidden">
      <StopCircle className="size-0" />
    </div>
  );
}
