type PaginationControlsProps = {
  total: number;
  offset: number;
  pageSize: number;
  customPage: string;
  currentPage: number;
  maxPage: number;
  loading: boolean;
  pageSizeOptions: readonly number[];
  onPageSizeChange: (next: number) => void;
  onCustomPageChange: (next: string) => void;
  onApplyCustomPage: () => void;
  onPrevious: () => void;
  onNext: () => void;
  previousDisabled: boolean;
  nextDisabled: boolean;
};

export const DEFAULT_PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

export function PaginationControls({
  total,
  offset,
  pageSize,
  customPage,
  currentPage,
  maxPage,
  loading,
  pageSizeOptions,
  onPageSizeChange,
  onCustomPageChange,
  onApplyCustomPage,
  onPrevious,
  onNext,
  previousDisabled,
  nextDisabled,
}: PaginationControlsProps) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
      <span className="text-muted-foreground text-xs">total={total} offset={offset} page={currentPage}/{maxPage}</span>
      <label className="text-xs text-muted-foreground">
        Page size
        <select
          className="ml-2 h-8 rounded-md border border-border bg-background px-2 text-xs"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          disabled={loading}
        >
          {pageSizeOptions.map((size) => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
      </label>
      <label className="text-xs text-muted-foreground">
        Page
        <input
          className="ml-2 h-8 w-20 rounded-md border border-border bg-background px-2 text-xs"
          type="number"
          min={1}
          max={Math.max(1, maxPage)}
          value={customPage}
          onChange={(event) => onCustomPageChange(event.target.value)}
          disabled={loading}
        />
      </label>
      <button
        type="button"
        className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-background px-2 text-xs"
        onClick={onApplyCustomPage}
        disabled={loading}
      >
        Go
      </button>
      <button
        type="button"
        className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-background px-2 text-xs"
        onClick={onPrevious}
        disabled={previousDisabled}
      >
        Prev
      </button>
      <button
        type="button"
        className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-background px-2 text-xs"
        onClick={onNext}
        disabled={nextDisabled}
      >
        Next
      </button>
    </div>
  );
}
