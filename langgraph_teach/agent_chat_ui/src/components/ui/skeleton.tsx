// NOTE  MC8yOmFIVnBZMlhtblk3a3ZiUG1yS002YTBkcFN3PT06ZTNmMTdkZTA=

import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("bg-primary/10 animate-pulse rounded-md", className)}
      {...props}
    />
  );
}
// FIXME  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002YTBkcFN3PT06ZTNmMTdkZTA=

export { Skeleton };
