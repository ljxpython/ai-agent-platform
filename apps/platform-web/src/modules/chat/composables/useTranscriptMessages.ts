import { computed, shallowReactive, shallowRef } from "vue";
import { useChannelEffect, useMessages, type AnyStream } from "@langchain/vue";
import { coerceMessageLikeToMessage, type BaseMessage } from "@langchain/core/messages";

/** SDK 1.10 root projection includes generic (non task/tools) subgraph text.
 * Use exact-scope values to distinguish returned answers from private child text.
 */
export function useTranscriptMessages(stream: AnyStream, namespace: readonly string[] = []) {
  const messages = useMessages(stream, () => ({ namespace }));
  const sources = shallowReactive(new Map<string, readonly string[]>());
  const scopedSnapshot = shallowRef<readonly BaseMessage[]>([]);
  const coerce = (value: unknown) => Array.isArray(value)
    ? value.map(message => coerceMessageLikeToMessage(message)) : [];
  useChannelEffect(stream, ["messages", "values"], {
    target: { namespace },
    replay: true,
    onEvent(event) {
      if (event.method === "values") {
        const value = event.params.data as { messages?: unknown };
        if (Array.isArray(value?.messages)) {
          for (const msg of value.messages) {
            const m = msg as { id?: string };
            if (m?.id && !sources.has(m.id)) sources.set(m.id, event.params.namespace);
          }
        }
        // Only this exact scope owns the snapshot; a descendant must not replace it.
        if (event.params.namespace.length === namespace.length && namespace.every((part, index) => event.params.namespace[index] === part)) {
          if (Array.isArray(value?.messages)) scopedSnapshot.value = coerce(value.messages);
        }
        return;
      }
      if (event.method !== "messages") return;
      const data = event.params.data as { id?: string; event?: string } | Array<{ id?: string }>;
      if (Array.isArray(data)) {
        for (const item of data) {
          if (item?.id && !sources.has(item.id)) sources.set(item.id, event.params.namespace);
        }
      } else if (data?.id && !sources.has(data.id)) {
        sources.set(data.id, event.params.namespace);
      }
    },
  });
  return computed(() => {
    // stream.values includes the SDK's merged message projection; only an exact
    // values event proves that the graph explicitly returned a child message.
    const rawValues = namespace.length === 0 && Array.isArray((stream.values.value as { messages?: unknown })?.messages)
      ? coerce((stream.values.value as { messages?: unknown }).messages)
      : [];
    const snapshot = scopedSnapshot.value.length ? scopedSnapshot.value : rawValues;
    const owned = new Map(snapshot.filter(message => message.id).map(message => [message.id!, message]));
    // Finished values are authoritative. Late replay chunks can leave the SDK's
    // message projection shorter than the checkpoint, even after the Run ends.
    const current = messages.value.map(message => !stream.isLoading.value && message.id && owned.has(message.id)
      ? owned.get(message.id)! : message);
    const seen = new Set(current.map(message => message.id));
    for (const message of snapshot) if (message.id && !seen.has(message.id)) current.push(message);
    const subagents = [...stream.subagents.value.values()].map(agent => agent.namespace);
    const children = [...stream.subgraphs.value.values(), ...stream.subagents.value.values()]
      .map(graph => graph.namespace)
      .filter(child => child.length > namespace.length && namespace.every((part, index) => child[index] === part));

    // Subagent delegated task inputs (passed as HumanMessage into child graphs)
    // should never leak into parent/root message streams.
    const subagentTaskInputs = new Set<string>();
    for (const agent of stream.subagents.value.values()) {
      if (typeof agent.taskInput === "string" && agent.taskInput.trim()) {
        subagentTaskInputs.add(agent.taskInput.trim());
      }
    }
    for (const msg of current) {
      const raw = msg as unknown as Record<string, unknown>;
      if (Array.isArray(raw.tool_calls)) {
        for (const tc of raw.tool_calls as Array<{ name?: string; args?: Record<string, unknown> }>) {
          if (tc?.name === "task" && tc.args && typeof tc.args === "object") {
            for (const key of ["description", "prompt", "task", "instructions"]) {
              const val = tc.args[key];
              if (typeof val === "string" && val.trim()) subagentTaskInputs.add(val.trim());
            }
          }
        }
      }
    }

    const isSameNamespace = (source?: readonly string[]) =>
      !source || (source.length === namespace.length && source.every((part, index) => namespace[index] === part));
    const getMsgType = (msg: BaseMessage) =>
      msg.type || (typeof (msg as unknown as { _getType?: () => string })._getType === "function"
        ? (msg as unknown as { _getType: () => string })._getType()
        : "");
    const hasToolCalls = (msg: BaseMessage) => {
      const raw = msg as unknown as Record<string, unknown>;
      return Array.isArray(raw.tool_calls) && raw.tool_calls.length > 0;
    };

    // Detect mid-stream model retries: if an uncommitted tool-less AI message in the current
    // namespace is followed by another AI message before any human/tool message, the earlier
    // attempt timed out or failed and was superseded by the retry.
    const supersededRetryIds = new Set<string>();
    let pendingToollessAiId: string | undefined;
    for (const msg of current) {
      const type = getMsgType(msg);
      const source = msg.id ? sources.get(msg.id) : undefined;
      if (!isSameNamespace(source)) continue;
      if (type === "human" || type === "tool") {
        pendingToollessAiId = undefined;
      } else if (type === "ai") {
        if (pendingToollessAiId) supersededRetryIds.add(pendingToollessAiId);
        pendingToollessAiId = msg.id && !owned.has(msg.id) && !hasToolCalls(msg) ? msg.id : undefined;
      }
    }

    return current.filter(message => {
      // 1. A child result explicitly promoted to parent values is an owned parent reply.
      if (message.id && owned.has(message.id)) return true;

      // Drop aborted/retried AI messages superseded by a subsequent retry attempt.
      if (message.id && supersededRetryIds.has(message.id)) return false;

      const source = message.id ? sources.get(message.id) : undefined;

      // Once a run finishes and authoritative values snapshot is present, any same-scope
      // message missing from snapshot is an uncommitted/aborted draft and must be dropped.
      if (!stream.isLoading.value && snapshot.length > 0 && isSameNamespace(source)) return false;

      // 2. Subagent messages (originating from child namespaces in stream.subagents, or child tools:/task: namespaces)
      // MUST NEVER leak into the parent transcript view, whether tool call, tool result, or text.
      // Note: root/same-namespace messages have source.length <= namespace.length (e.g. source = []),
      // and [].every(...) is vacuously true in JS, so we MUST require source.length > namespace.length.
      const isFromSubagent = !!source && source.length > namespace.length && (
        subagents.some(sub => sub.length > namespace.length && sub.length >= source.length && source.every((part, index) => sub[index] === part)) ||
        source.slice(namespace.length).some(part => part.startsWith("tools:") || part.startsWith("task:"))
      );
      if (isFromSubagent) return false;

      // 3. Filter out subagent task input HumanMessages from parent/root view even before source resolution
      const isHuman = getMsgType(message) === "human";
      if (isHuman) {
        const text = typeof message.content === "string"
          ? message.content.trim()
          : Array.isArray(message.content)
            ? message.content.map(b => (b && typeof b === "object" && "text" in b) ? String((b as { text?: unknown }).text ?? "") : "").join("").trim()
            : "";
        if (text && subagentTaskInputs.has(text) && namespace.length === 0) return false;
        if (source && children.some(child => child.every((part, index) => source[index] === part))) return false;
      }

      // 4. Execution subgraphs (non-subagent internal graph nodes) tool calls are preserved for root visibility
      if (hasToolCalls(message)) return true;
      if (message.type === "tool") return true;

      // 5. Default: include if it has no descendant source and is not from a child scope
      return !source || !children.some(child => child.every((part, index) => source[index] === part));
    });
  });
}
