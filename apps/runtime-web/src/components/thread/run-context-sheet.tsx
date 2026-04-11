import { Button } from "../ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "../ui/sheet";

export function RunContextSheet({
  open,
  onOpenChange,
  text,
  onTextChange,
  hasSavedContext,
  hasUnsavedChanges,
  onFormat,
  onSave,
  onClear,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  text: string;
  onTextChange: (value: string) => void;
  hasSavedContext: boolean;
  hasUnsavedChanges: boolean;
  onFormat: () => void;
  onSave: () => void;
  onClear: () => void;
}) {
  const statusLabel = hasUnsavedChanges
    ? "unsaved changes"
    : hasSavedContext
      ? "saved"
      : "not saved";

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
    >
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg"
      >
        <SheetHeader>
          <SheetTitle>Run Context</SheetTitle>
          <SheetDescription>
            Optional JSON object sent as the run {"`context`"} payload. This UI
            stays graph-agnostic and only does minimal JSON-object validation.
          </SheetDescription>
        </SheetHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4">
          <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            Saved manual context will be shallow-merged with artifact context at
            submit time, and manual values win on key collision.
          </div>

          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Status: {statusLabel}
            </span>
            <span className="text-muted-foreground">
              Empty text means manual context is disabled.
            </span>
          </div>

          <textarea
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
            spellCheck={false}
            placeholder={`{\n  "project_id": "00000000-0000-0000-0000-000000000001",\n  "model_id": "deepseek_chat",\n  "enable_tools": true\n}`}
            className="min-h-[360px] flex-1 resize-none rounded-md border bg-background p-3 font-mono text-sm shadow-xs outline-none focus:ring-2 focus:ring-ring/30"
          />
        </div>

        <SheetFooter className="border-t">
          <div className="flex w-full flex-wrap items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onFormat}
            >
              Format
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={onClear}
            >
              Clear
            </Button>
            <Button
              type="button"
              onClick={onSave}
            >
              Save
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
