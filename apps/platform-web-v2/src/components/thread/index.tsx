import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowDown,
  BadgeInfo,
  ChevronDown,
  ChevronUp,
  LoaderCircle,
  PanelRightOpen,
  PanelRightClose,
  Plus,
  SlidersHorizontal,
  SquarePen,
  XIcon,
} from "lucide-react";
import { parseAsBoolean, useQueryState } from "nuqs";
import type { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { v4 as uuidv4 } from "uuid";

import { useFileUpload } from "@/hooks/use-file-upload";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import {
  listRuntimeModels,
  listRuntimeTools,
  type RuntimeModelItem,
  type RuntimeToolItem,
} from "@/lib/management-api/runtime";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";
import { ArtifactContent, ArtifactTitle, useArtifactContext, useArtifactOpen } from "./artifact";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import ThreadHistory from "./history";
import { TasksFilesPanel } from "./tasks-files-panel";
import { ThreadIdCopyable } from "./agent-inbox/components/thread-id";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { GitHubSVG } from "../icons/github";
import { LangGraphLogoSVG } from "../icons/langgraph";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "../ui/sheet";
import { Switch } from "../ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

function StickyToBottomContent(props: {
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className={props.className}
    >
      <div
        ref={context.contentRef}
        className={props.contentClassName}
      >
        {props.content}
      </div>
      {props.footer}
    </div>
  );
}

function ScrollToBottom(props: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();
  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      className={props.className}
      onClick={() => scrollToBottom()}
    >
      <ArrowDown className="h-4 w-4" />
      <span>Scroll to bottom</span>
    </Button>
  );
}

function OpenGitHubRepo() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <a
            href="https://github.com/ljxpython/ai-agent-platform"
            target="_blank"
            rel="noreferrer noopener"
            className="flex items-center justify-center"
          >
            <GitHubSVG
              width="24"
              height="24"
            />
          </a>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>Open GitHub repo</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function hasPendingTaskToolCall(messages: Message[]): boolean {
  const resolvedToolCallIds = new Set<string>();

  for (const message of messages) {
    if (
      message.type === "tool" &&
      typeof message.tool_call_id === "string" &&
      message.tool_call_id.trim()
    ) {
      resolvedToolCallIds.add(message.tool_call_id);
    }
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.type !== "ai" || !Array.isArray(message.tool_calls)) {
      continue;
    }

    for (const toolCall of message.tool_calls) {
      if (!toolCall) {
        continue;
      }
      const unresolved = !toolCall.id || !resolvedToolCallIds.has(toolCall.id);
      if (unresolved && toolCall.name === "task") {
        return true;
      }
    }
  }

  return false;
}

type ThreadFeatures = {
  allowRunOptions?: boolean;
  showHistory?: boolean;
  showArtifacts?: boolean;
  showContextBar?: boolean;
};

type ThreadSlots = {
  headerSlot?: ReactNode;
  contextSlot?: ReactNode;
  emptyStateSlot?: ReactNode;
  rightPanelSlot?: ReactNode;
};

export function Thread({
  title = "Agent Chat",
  description,
  emptyTitle,
  emptyDescription,
  initialAssistantId = "",
  initialGraphId = "",
  initialTargetType = "assistant",
  features,
  slots,
}: {
  title?: string;
  description?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  initialAssistantId?: string;
  initialGraphId?: string;
  initialTargetType?: "assistant" | "graph";
  features?: ThreadFeatures;
  slots?: ThreadSlots;
}) {
  const prefersReducedMotion = useReducedMotion();
  const [artifactContext, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();
  const [threadId, _setThreadId] = useQueryState("threadId");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [chatAssistantId] = useQueryState("assistantId", { defaultValue: initialAssistantId });
  const [targetType] = useQueryState("targetType", { defaultValue: initialTargetType });
  const [chatGraphId] = useQueryState("graphId", { defaultValue: initialGraphId });
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const [debugMode, setDebugMode] = useQueryState(
    "debugMode",
    parseAsBoolean.withDefault(false),
  );
  const [input, setInput] = useState("");
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks: _resetBlocks,
    dragOver,
    handlePaste,
  } = useFileUpload();
  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const [advancedOptionsOpen, setAdvancedOptionsOpen] = useState(false);
  const [runtimeModels, setRuntimeModels] = useState<RuntimeModelItem[]>([]);
  const [runtimeTools, setRuntimeTools] = useState<RuntimeToolItem[]>([]);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [draftRuntimeModelId, setDraftRuntimeModelId] = useState("");
  const [draftRuntimeEnableTools, setDraftRuntimeEnableTools] = useState(false);
  const [draftRuntimeToolNames, setDraftRuntimeToolNames] = useState<string[]>([]);
  const [draftTemperatureInput, setDraftTemperatureInput] = useState("");
  const [draftMaxTokensInput, setDraftMaxTokensInput] = useState("");
  const [appliedRunOptions, setAppliedRunOptions] = useState({
    modelId: "",
    enableTools: false,
    toolNames: [] as string[],
    temperature: "",
    maxTokens: "",
  });
  const [contextBarCollapsed, setContextBarCollapsed] = useState(true);
  const { projectId } = useWorkspaceContext();
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const stream = useStreamContext();
  const messages = stream.messages;
  const isLoading = stream.isLoading;
  const lastError = useRef<string | undefined>(undefined);
  const allowRunOptions = features?.allowRunOptions ?? true;
  const showHistory = features?.showHistory ?? true;
  const showArtifacts = features?.showArtifacts ?? true;
  const allowContextBar = features?.showContextBar ?? true;

  const setThreadId = (id: string | null) => {
    _setThreadId(id);
    closeArtifact();
    setArtifactContext({});
  };

  useEffect(() => {
    if (!allowRunOptions) {
      setRuntimeModels([]);
      setRuntimeTools([]);
      setRuntimeLoading(false);
      setRuntimeError(null);
      return;
    }
    let cancelled = false;
    async function loadRuntimeCapabilities() {
      setRuntimeLoading(true);
      setRuntimeError(null);
      try {
        const [models, tools] = await Promise.all([
          listRuntimeModels().catch(() => null),
          listRuntimeTools().catch(() => null),
        ]);
        if (cancelled) {
          return;
        }
        const nextModels = models && Array.isArray(models.models) ? models.models : [];
        const nextTools = tools && Array.isArray(tools.tools) ? tools.tools : [];
        setRuntimeModels(nextModels);
        setRuntimeTools(nextTools);
        if (!appliedRunOptions.modelId) {
          const defaultModel = nextModels.find((item) => item.is_default)?.model_id || "";
          if (defaultModel) {
            setDraftRuntimeModelId(defaultModel);
          }
        }
      } catch (error) {
        if (!cancelled) {
          setRuntimeError(error instanceof Error ? error.message : "Failed to load runtime capabilities");
          setRuntimeModels([]);
          setRuntimeTools([]);
        }
      } finally {
        if (!cancelled) {
          setRuntimeLoading(false);
        }
      }
    }

    void loadRuntimeCapabilities();

    return () => {
      cancelled = true;
    };
  }, [allowRunOptions, appliedRunOptions.modelId]);

  useEffect(() => {
    if (!advancedOptionsOpen) {
      return;
    }
    setDraftRuntimeModelId(appliedRunOptions.modelId);
    setDraftRuntimeEnableTools(appliedRunOptions.enableTools);
    setDraftRuntimeToolNames(appliedRunOptions.toolNames);
    setDraftTemperatureInput(appliedRunOptions.temperature);
    setDraftMaxTokensInput(appliedRunOptions.maxTokens);
  }, [advancedOptionsOpen, appliedRunOptions]);

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message =
        typeof stream.error === "object" &&
        stream.error !== null &&
        "message" in stream.error &&
        typeof stream.error.message === "string"
          ? stream.error.message
          : undefined;
      if (!message || lastError.current === message) {
        return;
      }
      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  function toggleRuntimeTool(toolName: string) {
    setDraftRuntimeToolNames((prev) =>
      prev.includes(toolName)
        ? prev.filter((name) => name !== toolName)
        : [...prev, toolName],
    );
  }

  function buildRunConfig(): Record<string, unknown> | undefined {
    const configurable: Record<string, unknown> = {};
    const trimmedModelId = appliedRunOptions.modelId.trim();
    if (trimmedModelId) {
      configurable.model_id = trimmedModelId;
    }
    if (appliedRunOptions.enableTools && appliedRunOptions.toolNames.length > 0) {
      configurable.enable_tools = true;
      configurable.tools = appliedRunOptions.toolNames;
    }
    const normalizedTemperature = appliedRunOptions.temperature.trim();
    if (normalizedTemperature) {
      const parsedTemperature = Number(normalizedTemperature);
      if (Number.isFinite(parsedTemperature)) {
        configurable.temperature = parsedTemperature;
      }
    }
    const normalizedMaxTokens = appliedRunOptions.maxTokens.trim();
    if (normalizedMaxTokens) {
      const parsedMaxTokens = Number(normalizedMaxTokens);
      if (Number.isFinite(parsedMaxTokens)) {
        configurable.max_tokens = parsedMaxTokens;
      }
    }
    if (Object.keys(configurable).length === 0) {
      return undefined;
    }
    return { configurable };
  }

  function hasAppliedRunOptions(): boolean {
    return Boolean(
      appliedRunOptions.modelId.trim() ||
        (appliedRunOptions.enableTools && appliedRunOptions.toolNames.length > 0) ||
        appliedRunOptions.temperature.trim() ||
        appliedRunOptions.maxTokens.trim(),
    );
  }

  function applyRunOptions() {
    setAppliedRunOptions({
      modelId: draftRuntimeModelId,
      enableTools: draftRuntimeEnableTools,
      toolNames: draftRuntimeToolNames,
      temperature: draftTemperatureInput,
      maxTokens: draftMaxTokensInput,
    });
    setAdvancedOptionsOpen(false);
    toast.success("Run options applied for subsequent messages");
  }

  function cancelRunOptions() {
    setDraftRuntimeModelId(appliedRunOptions.modelId);
    setDraftRuntimeEnableTools(appliedRunOptions.enableTools);
    setDraftRuntimeToolNames(appliedRunOptions.toolNames);
    setDraftTemperatureInput(appliedRunOptions.temperature);
    setDraftMaxTokensInput(appliedRunOptions.maxTokens);
    setAdvancedOptionsOpen(false);
  }

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    if (
      messages.length !== prevMessageLength.current &&
      messages?.length &&
      messages[messages.length - 1].type === "ai"
    ) {
      setFirstTokenReceived(true);
    }
    prevMessageLength.current = messages.length;
  }, [messages]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((input.trim().length === 0 && contentBlocks.length === 0) || isLoading)
      return;
    setFirstTokenReceived(false);
    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: [
        ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
        ...contentBlocks,
      ] as Message["content"],
    };
    const toolMessages = ensureToolCallsHaveResponses(stream.messages);
    const context =
      Object.keys(artifactContext).length > 0 ? artifactContext : undefined;
    const config = buildRunConfig();
    stream.submit(
      { messages: [...toolMessages, newHumanMessage], context },
      {
        config,
        ...(debugMode ? { interruptBefore: ["tools"] } : {}),
        streamMode: ["values"],
        streamSubgraphs: true,
        streamResumable: true,
        optimisticValues: (prev) => ({
          ...prev,
          context,
          messages: [
            ...(prev.messages ?? []),
            ...toolMessages,
            newHumanMessage,
          ],
        }),
      },
    );
    setInput("");
    setContentBlocks([]);
  };

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
    const config = buildRunConfig();
    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      config,
      ...(debugMode ? { interruptBefore: ["tools"] } : {}),
      streamMode: ["values"],
      streamSubgraphs: true,
      streamResumable: true,
    });
  };

  const canContinueDebugStream =
    Boolean(debugMode) &&
    Boolean(stream.interrupt) &&
    !isAgentInboxInterruptSchema(stream.interrupt);

  const handleContinueStream = () => {
    if (!canContinueDebugStream || isLoading) {
      return;
    }

    const config = buildRunConfig();
    const hasTaskToolCall = hasPendingTaskToolCall(stream.messages);
    stream.submit(undefined, {
      config,
      ...(hasTaskToolCall
        ? { interruptAfter: ["tools"] }
        : { interruptBefore: ["tools"] }),
      streamMode: ["values"],
      streamSubgraphs: true,
      streamResumable: true,
    });
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const shouldRenderStandaloneInterrupt =
    chatStarted && hasNoAIOrToolMessages && Boolean(stream.interrupt);
  const shellSpringTransition =
    !prefersReducedMotion && isLargeScreen
      ? { type: "spring" as const, stiffness: 300, damping: 30 }
      : { duration: 0 };
  const logoSpringTransition = prefersReducedMotion
    ? { duration: 0 }
    : { type: "spring" as const, stiffness: 300, damping: 30 };
  const normalizedTargetType = targetType === "graph" ? "graph" : "assistant";
  const activeGraphId = normalizedTargetType === "graph" ? chatGraphId || chatAssistantId : chatGraphId;
  const activeAssistantId = normalizedTargetType === "assistant" ? chatAssistantId : "";
  const sourceLabel = threadId
    ? "From Thread"
    : normalizedTargetType === "graph"
    ? "From Graph"
      : "From Assistant";
  const showContextBar = allowContextBar && Boolean(projectId || activeGraphId || activeAssistantId || threadId);
  const artifactColumnVisible = useMemo(
    () => (showArtifacts && artifactOpen) || Boolean(slots?.rightPanelSlot),
    [artifactOpen, showArtifacts, slots?.rightPanelSlot],
  );
  const effectiveEmptyTitle = emptyTitle || title;
  const effectiveEmptyDescription = emptyDescription || description;
  const contextPanel = showContextBar ? <ChatContextPanel
    sourceLabel={sourceLabel}
    graphId={activeGraphId}
    assistantId={activeAssistantId}
    threadId={threadId || ""}
    collapsed={contextBarCollapsed}
    onToggleCollapsed={() => setContextBarCollapsed((prev) => !prev)}
    extraContent={slots?.contextSlot}
  /> : null;

  return (
    <div className="flex min-h-0 w-full flex-1 overflow-hidden">
      {showHistory ? <div className="relative hidden lg:flex">
        <motion.div
          className="absolute z-20 h-full overflow-hidden border-r border-border/80 bg-card/90 backdrop-blur"
          style={{ width: 300 }}
          animate={{
            x: chatHistoryOpen ? 0 : -300,
          }}
          initial={{ x: -300 }}
          transition={shellSpringTransition}
        >
          <div
            className="relative h-full"
            style={{ width: 300 }}
          >
            <ThreadHistory />
          </div>
        </motion.div>
      </div> : null}

      <div
        className={cn(
          "grid w-full grid-cols-[1fr_0fr] transition-all motion-standard",
          artifactColumnVisible && "grid-cols-[3fr_2fr]",
        )}
      >
        <motion.div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}
          layout={isLargeScreen && !prefersReducedMotion}
          animate={{
            marginLeft: showHistory && chatHistoryOpen ? (isLargeScreen ? 300 : 0) : 0,
            width: showHistory && chatHistoryOpen
              ? isLargeScreen
                ? "calc(100% - 300px)"
                : "100%"
              : "100%",
          }}
          transition={shellSpringTransition}
        >
            {!chatStarted && (
              <div className="absolute top-0 left-0 z-10 flex w-full items-center justify-between gap-3 p-2 pl-4">
                <div>
                {showHistory && (!chatHistoryOpen || !isLargeScreen) && (
                  <Button
                    className="hover:bg-accent hover:text-accent-foreground"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                )}
              </div>
              <div className="absolute top-2 right-4 flex items-center">
                <OpenGitHubRepo />
              </div>
              {slots?.headerSlot ? (
                <div className="absolute top-2 left-16 right-20 z-10 flex justify-center px-4">
                  {slots.headerSlot}
                </div>
              ) : null}
              {showContextBar ? (
                <div className="absolute top-14 left-4 max-w-[calc(100%-2rem)]">
                  {contextPanel}
                </div>
              ) : slots?.contextSlot ? (
                <div className="absolute top-14 left-4 max-w-[calc(100%-2rem)]">
                  <div className="max-w-full">{slots.contextSlot}</div>
                </div>
              ) : null}
            </div>
          )}
          {chatStarted && (
            <div className="relative z-10 flex items-start justify-between gap-3 p-2">
              <div className="relative flex min-w-0 flex-1 items-start justify-start gap-2">
                <div className="absolute left-0 z-10">
                  {showHistory && (!chatHistoryOpen || !isLargeScreen) && (
                    <Button
                      className="hover:bg-accent hover:text-accent-foreground"
                      variant="ghost"
                      onClick={() => setChatHistoryOpen((p) => !p)}
                    >
                      {chatHistoryOpen ? (
                        <PanelRightOpen className="size-5" />
                      ) : (
                        <PanelRightClose className="size-5" />
                      )}
                    </Button>
                  )}
                </div>
                <motion.div
                  className="flex min-w-0 flex-col gap-2"
                  animate={{
                    marginLeft: !chatHistoryOpen ? 48 : 0,
                  }}
                  transition={logoSpringTransition}
                >
                  <motion.button
                    className="flex cursor-pointer items-center gap-2"
                    onClick={() => setThreadId(null)}
                  >
                    <LangGraphLogoSVG width={32} height={32} />
                    <span className="text-xl font-semibold tracking-tight">
                      {title}
                    </span>
                  </motion.button>
                  {slots?.headerSlot ? <div className="max-w-full">{slots.headerSlot}</div> : null}
                  {contextPanel ? contextPanel : slots?.contextSlot ? <div className="max-w-full">{slots.contextSlot}</div> : null}
                </motion.div>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center">
                  <OpenGitHubRepo />
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
                  onClick={() => setThreadId(null)}
                >
                  <SquarePen className="size-5" />
                  <span>New Chat</span>
                </Button>
              </div>
            </div>
          )}

          <StickToBottom className="relative flex-1 overflow-hidden">
            <StickyToBottomContent
              className={cn(
                "absolute inset-0 overflow-y-scroll px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted && "mt-[25vh] flex flex-col items-stretch",
                chatStarted && "grid grid-rows-[1fr_auto]",
              )}
              contentClassName="pt-8 pb-16 max-w-3xl mx-auto flex flex-col gap-4 w-full"
              content={
                <>
                  {messages
                    .filter((m) => !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX))
                    .map((message, index) =>
                      message.type === "human" ? (
                        <HumanMessage
                          key={message.id || `${message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                        />
                      ) : (
                        <AssistantMessage
                          key={message.id || `${message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                          handleRegenerate={handleRegenerate}
                        />
                      ),
                    )}
                  {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                  {shouldRenderStandaloneInterrupt && (
                    <AssistantMessage
                      key="interrupt-msg"
                      message={undefined}
                      isLoading={isLoading}
                      handleRegenerate={handleRegenerate}
                    />
                  )}
                  {isLoading && !firstTokenReceived && (
                    <AssistantMessageLoading />
                  )}
                </>
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-6 bg-background/95 backdrop-blur">
                  {!chatStarted && (
                    <div className="flex items-center gap-3">
                      <LangGraphLogoSVG className="h-8 flex-shrink-0" />
                      <div className="flex flex-col gap-1">
                        <h1 className="text-2xl font-semibold tracking-tight">
                          {effectiveEmptyTitle}
                        </h1>
                        {effectiveEmptyDescription ? (
                          <p className="text-muted-foreground max-w-2xl text-sm">
                            {effectiveEmptyDescription}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  )}

                  {!chatStarted && slots?.emptyStateSlot ? (
                    <div className="w-full max-w-3xl px-1 pb-2">{slots.emptyStateSlot}</div>
                  ) : null}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    ref={dropRef}
                    className={cn(
                      "bg-card relative z-10 mx-auto mb-6 w-full max-w-3xl rounded-2xl border border-border/80 shadow-sm transition-all motion-micro",
                      dragOver
                        ? "border-primary border-2 border-dotted"
                        : "border border-solid",
                    )}
                  >
                    {allowRunOptions ? <Sheet open={advancedOptionsOpen} onOpenChange={setAdvancedOptionsOpen}>
                      <SheetContent side={isLargeScreen ? "right" : "bottom"} className="overflow-y-auto sm:max-w-xl">
                        <SheetHeader>
                          <SheetTitle>Run options</SheetTitle>
                          <SheetDescription>
                            These overrides apply only to subsequent messages in the current chat session and do not modify assistant defaults.
                          </SheetDescription>
                        </SheetHeader>

                        <div className="grid gap-4 px-4 pb-4">
                          <div className="grid gap-3 lg:grid-cols-2">
                            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                              Model
                              <select
                                id="runtime-model-id"
                                className="bg-background border-input ring-offset-background focus-visible:ring-ring flex h-9 w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
                                value={draftRuntimeModelId}
                                onChange={(event) => setDraftRuntimeModelId(event.target.value)}
                                disabled={runtimeLoading}
                              >
                                <option value="">Use assistant default</option>
                                {runtimeModels.map((model) => (
                                  <option key={model.model_id} value={model.model_id}>
                                    {model.display_name || model.model_id}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <div className="grid gap-1.5">
                              <div className="flex items-center space-x-2">
                                <Switch
                                  id="runtime-enable-tools"
                                  checked={draftRuntimeEnableTools}
                                  onCheckedChange={setDraftRuntimeEnableTools}
                                />
                                <Label htmlFor="runtime-enable-tools" className="text-sm text-muted-foreground">
                                  Enable tools for this run
                                </Label>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Toggle runtime tools without persisting anything to the assistant.
                              </p>
                            </div>
                          </div>

                          <div className="grid gap-3 lg:grid-cols-2">
                            <label htmlFor="runtime-temperature" className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                              Temperature
                              <Input
                                id="runtime-temperature"
                                value={draftTemperatureInput}
                                onChange={(event) => setDraftTemperatureInput(event.target.value)}
                                placeholder="Use assistant default"
                                inputMode="decimal"
                              />
                            </label>
                            <label htmlFor="runtime-max-tokens" className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                              Max tokens
                              <Input
                                id="runtime-max-tokens"
                                value={draftMaxTokensInput}
                                onChange={(event) => setDraftMaxTokensInput(event.target.value)}
                                placeholder="Use assistant default"
                                inputMode="numeric"
                              />
                            </label>
                          </div>

                          <div className="grid gap-2">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-xs font-medium text-muted-foreground">Tools</p>
                              <button
                                type="button"
                                className="text-xs text-muted-foreground underline-offset-4 hover:underline"
                                onClick={() => setDraftRuntimeToolNames([])}
                              >
                                Clear tools
                              </button>
                            </div>
                            {runtimeError ? <p className="text-xs text-amber-700">{runtimeError}</p> : null}
                            <div className="flex flex-wrap gap-2">
                              {runtimeTools.length > 0 ? (
                                runtimeTools.map((tool) => {
                                  const selected = draftRuntimeToolNames.includes(tool.name);
                                  return (
                                    <button
                                      key={tool.name}
                                      type="button"
                                      className={cn(
                                        "inline-flex h-8 items-center rounded-md border px-2 text-xs transition-colors",
                                        selected
                                          ? "border-primary bg-primary/10 text-foreground"
                                          : "border-border bg-background text-muted-foreground hover:text-foreground",
                                      )}
                                      onClick={() => toggleRuntimeTool(tool.name)}
                                      disabled={!draftRuntimeEnableTools}
                                      title={tool.description || tool.name}
                                    >
                                      {tool.name}
                                    </button>
                                  );
                                })
                              ) : (
                                <p className="text-xs text-muted-foreground">
                                  {runtimeLoading ? "Loading runtime tools..." : "No runtime tools available."}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>

                        <SheetFooter>
                          <Button type="button" variant="outline" onClick={cancelRunOptions}>
                            Cancel
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                              setDraftRuntimeModelId("");
                              setDraftRuntimeEnableTools(false);
                              setDraftRuntimeToolNames([]);
                              setDraftTemperatureInput("");
                              setDraftMaxTokensInput("");
                            }}
                          >
                            Reset Draft
                          </Button>
                          <Button type="button" onClick={applyRunOptions}>
                            Confirm Run Options
                          </Button>
                        </SheetFooter>
                      </SheetContent>
                    </Sheet> : null}
                    <form
                      onSubmit={handleSubmit}
                      className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2"
                    >
                      <TasksFilesPanel
                        values={stream.values as Record<string, unknown> | undefined}
                        isRunning={isLoading}
                        hasInterrupt={Boolean(stream.interrupt)}
                      />
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      {allowRunOptions ? <div className="px-3 pt-3">
                        <button
                          type="button"
                          className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                          onClick={() => setAdvancedOptionsOpen((prev) => !prev)}
                        >
                          <SlidersHorizontal className="size-4" />
                          <span>Run options</span>
                          {hasAppliedRunOptions() ? (
                            <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-foreground">
                              Applied
                            </span>
                          ) : null}
                          {advancedOptionsOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                        </button>
                      </div> : null}
                      <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="Type your message..."
                        className="field-sizing-content resize-none border-none bg-transparent p-3.5 pb-0 shadow-none ring-0 outline-none focus:ring-0 focus:outline-none"
                      />
                      <div className="flex items-center gap-6 p-2 pt-4">
                        <div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="render-tool-calls"
                              checked={hideToolCalls ?? false}
                              onCheckedChange={setHideToolCalls}
                            />
                            <Label
                              htmlFor="render-tool-calls"
                              className="text-sm text-muted-foreground"
                            >
                              Hide Tool Calls
                            </Label>
                          </div>
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <Switch
                              id="debug-mode"
                              checked={debugMode ?? false}
                              onCheckedChange={setDebugMode}
                            />
                            <Label
                              htmlFor="debug-mode"
                              className="text-sm text-muted-foreground"
                            >
                              Debug Mode
                            </Label>
                          </div>
                        </div>
                        <Label
                          htmlFor="file-input"
                          className="flex cursor-pointer items-center gap-2"
                        >
                          <Plus className="size-5 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">
                            Upload PDF or Image
                          </span>
                        </Label>
                        <input
                          id="file-input"
                          type="file"
                          onChange={handleFileUpload}
                          multiple
                          accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                          className="hidden"
                        />
                        {stream.isLoading ? (
                          <Button
                            key="stop"
                            onClick={() => stream.stop()}
                            className="ml-auto"
                          >
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                            Cancel
                          </Button>
                        ) : (
                          <div className="ml-auto flex items-center gap-2">
                            {canContinueDebugStream ? (
                              <Button
                                type="button"
                                variant="outline"
                                onClick={handleContinueStream}
                              >
                                Continue
                              </Button>
                            ) : null}
                            <Button
                              type="submit"
                              className="shadow-md transition-all motion-micro"
                              disabled={
                                isLoading ||
                                canContinueDebugStream ||
                                (!input.trim() && contentBlocks.length === 0)
                              }
                            >
                              {debugMode ? "Step" : "Send"}
                            </Button>
                          </div>
                        )}
                      </div>
                    </form>
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </motion.div>
        {artifactColumnVisible ? (
          <div className={cn("relative flex flex-col", (showArtifacts && artifactOpen) || slots?.rightPanelSlot ? "border-l" : "") }>
            <div className="absolute inset-0 flex min-w-[30vw] flex-col">
              {showArtifacts && artifactOpen ? (
                <>
                  <div className="grid grid-cols-[1fr_auto] border-b p-4">
                    <ArtifactTitle className="truncate overflow-hidden" />
                    <button
                      type="button"
                      onClick={closeArtifact}
                      className="cursor-pointer"
                    >
                      <XIcon className="size-5" />
                    </button>
                  </div>
                  <ArtifactContent className="relative flex-grow" />
                </>
              ) : slots?.rightPanelSlot ? (
                <div className="flex h-full flex-col overflow-y-auto bg-card/40 p-4">
                  {slots.rightPanelSlot}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ContextChip({
  label,
  prominent = false,
}: {
  label: string;
  prominent?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center rounded-full border px-2 py-1 text-[10px] leading-none",
        prominent
          ? "border-primary/30 bg-primary/10 text-foreground"
          : "border-border/70 bg-background/70 font-mono text-muted-foreground",
      )}
      title={label}
    >
      <span className="truncate">{label}</span>
    </span>
  );
}

function ThreadContextChip({ threadId }: { threadId: string }) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-border/70 bg-background/70 px-2 py-1">
      <span className="font-mono text-[10px] leading-none text-muted-foreground">
        thread: {threadId}
      </span>
      <ThreadIdCopyable threadId={threadId} />
    </div>
  );
}

function ChatContextPanel({
  sourceLabel,
  graphId,
  assistantId,
  threadId,
  collapsed,
  onToggleCollapsed,
  extraContent,
}: {
  sourceLabel: string;
  graphId: string;
  assistantId: string;
  threadId: string;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  extraContent?: ReactNode;
}) {
  const summary = [graphId && `graph ${graphId}`, assistantId && `assistant ${assistantId}`, threadId && `thread ${threadId}`]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="inline-grid max-w-full gap-1 text-[11px] text-muted-foreground">
      {collapsed ? (
        <Button
          type="button"
          variant="ghost"
          className="text-muted-foreground hover:bg-muted hover:text-foreground h-8 w-8 rounded-full p-0"
          onClick={onToggleCollapsed}
          title={summary || sourceLabel}
        >
          <BadgeInfo className="size-4" />
        </Button>
      ) : (
        <div className="inline-grid max-w-full gap-1 rounded-lg border border-border/70 bg-background/80 px-3 py-2 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <ContextChip label={sourceLabel} prominent />
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground hover:bg-muted hover:text-foreground h-8 w-8 rounded-full p-0"
              onClick={onToggleCollapsed}
              title="Collapse chat context"
            >
              <BadgeInfo className="size-4" />
            </Button>
          </div>
          {graphId ? <ContextRow label="graph" value={graphId} /> : null}
          {assistantId ? <ContextRow label="assistant" value={assistantId} /> : null}
          {threadId ? (
            <div className="flex min-w-0 items-center gap-2">
              <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground/80">thread</span>
              <ThreadContextChip threadId={threadId} />
            </div>
          ) : null}
          {extraContent ? (
            <div className="mt-2 border-t border-border/60 pt-2">
              {extraContent}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground/80">{label}</span>
      <span className="max-w-[min(70vw,28rem)] truncate font-mono text-[11px] text-muted-foreground" title={value}>
        {value}
      </span>
    </div>
  );
}
