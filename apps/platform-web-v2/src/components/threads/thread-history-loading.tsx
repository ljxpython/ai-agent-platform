export function ThreadHistoryLoading() {
  return (
    <div className="grid gap-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={`thread-loading-${index + 1}`} className="h-16 animate-pulse rounded-lg border border-border/70 bg-muted/40" />
      ))}
    </div>
  );
}
