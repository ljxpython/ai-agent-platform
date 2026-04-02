import type { ManagementThread } from "@/lib/management-api/threads";

import { DEFAULT_PAGE_SIZE_OPTIONS, PaginationControls } from "@/components/platform/pagination-controls";
import { PageStateError } from "@/components/platform/page-state";

import { ThreadList } from "./thread-list";

export function ThreadListPanel({
  items,
  selectedThreadId,
  loading,
  total,
  limit,
  offset,
  error,
  customPage,
  currentPage,
  maxPage,
  onSelect,
  onPageSizeChange,
  onCustomPageChange,
  onApplyCustomPage,
  onPrevious,
  onNext,
}: {
  items: ManagementThread[];
  selectedThreadId?: string;
  loading?: boolean;
  total: number;
  limit: number;
  offset: number;
  error?: string | null;
  customPage: string;
  currentPage: number;
  maxPage: number;
  onSelect: (item: ManagementThread) => void;
  onPageSizeChange: (next: number) => void;
  onCustomPageChange: (next: string) => void;
  onApplyCustomPage: () => void;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <section className="grid self-start gap-4 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <h3 className="text-base font-semibold">Thread List</h3>
        <p className="mt-1 text-sm text-muted-foreground">Thread previews scoped to the current project and optional assistant/graph filters.</p>
      </div>
      {error ? <PageStateError className="mt-0" message={error} /> : null}
      <ThreadList items={items} selectedThreadId={selectedThreadId} loading={loading} onSelect={onSelect} />
      <PaginationControls
        total={total}
        offset={offset}
        pageSize={limit}
        customPage={customPage}
        currentPage={currentPage}
        maxPage={maxPage}
        loading={Boolean(loading)}
        pageSizeOptions={DEFAULT_PAGE_SIZE_OPTIONS}
        onPageSizeChange={onPageSizeChange}
        onCustomPageChange={onCustomPageChange}
        onApplyCustomPage={onApplyCustomPage}
        onPrevious={onPrevious}
        onNext={onNext}
        previousDisabled={Boolean(loading) || offset === 0}
        nextDisabled={Boolean(loading) || offset + limit >= total}
      />
    </section>
  );
}
