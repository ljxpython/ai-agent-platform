import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ManagementAssistant } from "@/lib/management-api/assistants";
import type { ManagementGraph } from "@/lib/management-api/graphs";

export function ThreadHistoryToolbar({
  previewQuery,
  threadIdQuery,
  assistantFilter,
  graphFilter,
  statusFilter,
  onPreviewQueryChange,
  onThreadIdQueryChange,
  onAssistantFilterChange,
  onGraphFilterChange,
  onStatusFilterChange,
  onSearch,
  onClear,
  onRefresh,
  assistantOptions,
  graphOptions,
  loading,
  searching,
  clearing,
  refreshing,
}: {
  previewQuery: string;
  threadIdQuery: string;
  assistantFilter: string;
  graphFilter: string;
  statusFilter: string;
  onPreviewQueryChange: (value: string) => void;
  onThreadIdQueryChange: (value: string) => void;
  onAssistantFilterChange: (value: string) => void;
  onGraphFilterChange: (value: string) => void;
  onStatusFilterChange: (value: string) => void;
  onSearch: () => void;
  onClear: () => void;
  onRefresh: () => void;
  assistantOptions: ManagementAssistant[];
  graphOptions: ManagementGraph[];
  loading?: boolean;
  searching?: boolean;
  clearing?: boolean;
  refreshing?: boolean;
}) {
  return (
    <div className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Threads</h2>
          <p className="mt-1 text-sm text-muted-foreground">Browse project-scoped thread history without affecting the live chat page.</p>
        </div>
      </div>

      <form
        className="grid gap-2 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.9fr)_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch();
        }}
      >
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="search preview text"
          value={previewQuery}
          onChange={(event) => onPreviewQueryChange(event.target.value)}
        />
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="thread id (fuzzy)"
          value={threadIdQuery}
          onChange={(event) => onThreadIdQueryChange(event.target.value)}
        />
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="assistant id or name"
          list="thread-assistant-options"
          value={assistantFilter}
          onChange={(event) => onAssistantFilterChange(event.target.value)}
        />
        <datalist id="thread-assistant-options">
          {assistantOptions.map((assistant) => (
            <option
              key={assistant.id}
              value={assistant.langgraph_assistant_id}
              label={assistant.name?.trim() ? `${assistant.langgraph_assistant_id} — ${assistant.name}` : assistant.langgraph_assistant_id}
            >
              {assistant.name?.trim() ? `${assistant.langgraph_assistant_id} — ${assistant.name}` : assistant.langgraph_assistant_id}
            </option>
          ))}
        </datalist>
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="graph id or description"
          list="thread-graph-options"
          value={graphFilter}
          onChange={(event) => onGraphFilterChange(event.target.value)}
        />
        <datalist id="thread-graph-options">
          {graphOptions.map((graph) => (
            <option
              key={graph.graph_id}
              value={graph.graph_id}
              label={graph.description?.trim() ? `${graph.graph_id} — ${graph.description}` : graph.graph_id}
            >
              {graph.description?.trim() ? `${graph.graph_id} — ${graph.description}` : graph.graph_id}
            </option>
          ))}
        </datalist>
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="status"
          value={statusFilter}
          onChange={(event) => onStatusFilterChange(event.target.value)}
        />
        <div className="flex flex-wrap items-center justify-end gap-2 xl:col-span-1">
          <Button
            type="submit"
            variant="outline"
            disabled={Boolean(loading || searching || clearing || refreshing)}
          >
            {searching ? <LoaderCircle className="animate-spin" /> : null}
            {searching ? "Searching..." : "Search"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onClear}
            disabled={Boolean(loading || searching || clearing || refreshing)}
          >
            {clearing ? <LoaderCircle className="animate-spin" /> : null}
            {clearing ? "Clearing..." : "Clear"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onRefresh}
            disabled={Boolean(loading || searching || clearing || refreshing)}
          >
            {refreshing ? <LoaderCircle className="animate-spin" /> : null}
            {refreshing ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </form>
    </div>
  );
}
