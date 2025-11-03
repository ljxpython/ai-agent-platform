import * as React from "react";
import * as SeparatorPrimitive from "@radix-ui/react-separator";
// TODO  MC8yOmFIVnBZMlhtblk3a3ZiUG1yS002ZVdreFFRPT06ZjMxZDE0Yzc=

import { cn } from "@/lib/utils";
// TODO  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002ZVdreFFRPT06ZjMxZDE0Yzc=

function Separator({
  className,
  orientation = "horizontal",
  decorative = true,
  ...props
}: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      data-slot="separator-root"
      decorative={decorative}
      orientation={orientation}
      className={cn(
        "bg-border shrink-0 data-[orientation=horizontal]:h-px data-[orientation=horizontal]:w-full data-[orientation=vertical]:h-full data-[orientation=vertical]:w-px",
        className,
      )}
      {...props}
    />
  );
}

export { Separator };
