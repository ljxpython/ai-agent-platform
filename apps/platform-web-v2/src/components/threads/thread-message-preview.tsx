import type { Message } from "@langchain/langgraph-sdk";

import { PageStateEmpty } from "@/components/platform/page-state";
import { getContentString } from "@/components/thread/utils";

export function ThreadMessagePreview({ messages }: { messages: Message[] }) {
  return (
    <section className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <h3 className="text-base font-semibold">Recent Messages</h3>
        <p className="mt-1 text-sm text-muted-foreground">Preview the latest messages captured in thread state.</p>
      </div>
      {messages.length === 0 ? (
        <PageStateEmpty className="mt-0" message="No messages found in current thread state." />
      ) : (
        <div className="grid gap-2">
          {messages.slice(-12).reverse().map((message) => (
            <div key={message.id} className="rounded-md border border-border/70 bg-background/60 p-3">
              <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{message.type}</div>
              <div className="text-sm whitespace-pre-wrap break-words">{getContentString(message.content)}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
