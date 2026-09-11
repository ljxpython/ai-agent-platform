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
        // Only this exact scope owns the snapshot; a descendant must not replace it.
        if (event.params.namespace.length === namespace.length && namespace.every((part, index) => event.params.namespace[index] === part)) {
          const value = event.params.data as { messages?: unknown };
          if (Array.isArray(value?.messages)) scopedSnapshot.value = coerce(value.messages);
        }
        return;
      }
      if (event.method !== "messages") return;
      const data = event.params.data;
      if (data.event === "message-start") sources.set(data.id, event.params.namespace);
    },
  });
  return computed(() => {
    // stream.values includes the SDK's merged message projection; only an exact
    // values event proves that the graph explicitly returned a child message.
    const snapshot = scopedSnapshot.value;
    const owned = new Map(snapshot.filter(message => message.id).map(message => [message.id!, message]));
    // Finished values are authoritative. Late replay chunks can leave the SDK's
    // message projection shorter than the checkpoint, even after the Run ends.
    const current = messages.value.map(message => !stream.isLoading.value && message.id && owned.has(message.id)
      ? owned.get(message.id)! : message);
    const seen = new Set(current.map(message => message.id));
    for (const message of snapshot) if (message.id && !seen.has(message.id)) current.push(message);
    const children = [...stream.subgraphs.value.values(), ...stream.subagents.value.values()]
      .map(graph => graph.namespace)
      .filter(child => child.length > namespace.length && namespace.every((part, index) => child[index] === part));
    return current.filter(message => {
      // A child result explicitly returned in parent values is a parent reply.
      if (message.id && owned.has(message.id)) return true;
      const source = message.id ? sources.get(message.id) : undefined;
      return !source || !children.some(child => child.every((part, index) => source[index] === part));
    });
  });
}
