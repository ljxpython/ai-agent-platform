"use client";

import { useEffect, useRef } from "react";

type ListSearchProps = {
  value: string;
  placeholder: string;
  debounceMs?: number;
  className?: string;
  onValueChange: (next: string) => void;
  onSearch: (keyword: string) => void;
  onClear: () => void;
};

export function ListSearch({
  value,
  placeholder,
  debounceMs = 300,
  className,
  onValueChange,
  onSearch,
  onClear,
}: ListSearchProps) {
  const lastCommittedRef = useRef<string>(value.trim());

  useEffect(() => {
    if (debounceMs <= 0) {
      return;
    }
    const timerId = window.setTimeout(() => {
      const normalized = value.trim();
      if (normalized === lastCommittedRef.current) {
        return;
      }
      onSearch(normalized);
      lastCommittedRef.current = normalized;
    }, debounceMs);
    return () => window.clearTimeout(timerId);
  }, [debounceMs, onSearch, value]);

  return (
    <form
      className={className || "mt-4 flex flex-wrap items-center gap-2"}
      onSubmit={(event) => {
        event.preventDefault();
        const normalized = value.trim();
        onSearch(normalized);
        lastCommittedRef.current = normalized;
      }}
    >
      <input
        className="h-9 w-64 rounded-md border border-border bg-background px-3 text-sm"
        placeholder={placeholder}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
      />
      <button
        type="submit"
        className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm"
      >
        Search
      </button>
      <button
        type="button"
        className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm"
        onClick={() => {
          onValueChange("");
          onClear();
          lastCommittedRef.current = "";
        }}
      >
        Clear
      </button>
    </form>
  );
}
