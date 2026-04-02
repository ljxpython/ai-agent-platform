import { toPrettyJson } from "@/lib/threads";

export function ThreadRawDataCard({
  metadata,
  values,
  state,
}: {
  metadata?: Record<string, unknown> | null;
  values?: Record<string, unknown> | null;
  state?: Record<string, unknown> | null;
}) {
  return (
    <section className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <h3 className="text-base font-semibold">Raw Data</h3>
        <p className="mt-1 text-sm text-muted-foreground">Useful for debugging metadata, persisted values, and current state snapshots.</p>
      </div>
      <JsonBlock title="Metadata" value={metadata} />
      <JsonBlock title="Values" value={values} />
      <JsonBlock title="State" value={state} />
    </section>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="grid gap-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <pre className="overflow-x-auto rounded-md border border-border/70 bg-background/60 p-3 text-xs whitespace-pre-wrap break-words">
        {toPrettyJson(value)}
      </pre>
    </div>
  );
}
