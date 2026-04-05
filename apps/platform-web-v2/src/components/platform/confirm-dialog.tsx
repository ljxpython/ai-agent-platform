import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function ConfirmDialog({
  confirmLabel = "Confirm",
  confirmLabelLoading = "Processing...",
  cancelLabel = "Cancel",
  description,
  loading = false,
  onCancel,
  onConfirm,
  open,
  title,
}: {
  confirmLabel?: string;
  confirmLabelLoading?: string;
  cancelLabel?: string;
  description?: ReactNode;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  open: boolean;
  title: string;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => (!nextOpen ? onCancel() : undefined)}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? (
            <DialogDescription>{description}</DialogDescription>
          ) : null}
        </DialogHeader>

        <DialogFooter>
          <Button
            disabled={loading}
            type="button"
            variant="ghost"
            onClick={onCancel}
          >
            {cancelLabel}
          </Button>
          <Button
            disabled={loading}
            style={{
              background: "var(--status-danger-foreground)",
              color: "#ffffff",
              borderColor: "transparent",
            }}
            type="button"
            variant="ghost"
            onClick={onConfirm}
          >
            {loading ? confirmLabelLoading : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
