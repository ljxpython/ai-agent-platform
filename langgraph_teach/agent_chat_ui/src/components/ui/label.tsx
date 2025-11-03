import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
// TODO  MC8yOmFIVnBZMlhtblk3a3ZiUG1yS002WXpFM1FRPT06YmE2ZmVhOTI=

import { cn } from "@/lib/utils";
// @ts-expect-error  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002WXpFM1FRPT06YmE2ZmVhOTI=

function Label({
  className,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Label };
