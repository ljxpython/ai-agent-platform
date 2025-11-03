import * as React from "react";
import * as AvatarPrimitive from "@radix-ui/react-avatar";
// @ts-expect-error  MC8zOmFIVnBZMlhtblk3a3ZiUG1yS002VVRWcWJBPT06OTUxNGI4ZTY=

import { cn } from "@/lib/utils";

function Avatar({
  className,
  ...props
}: React.ComponentProps<typeof AvatarPrimitive.Root>) {
  return (
    <AvatarPrimitive.Root
      data-slot="avatar"
      className={cn(
        "relative flex size-8 shrink-0 overflow-hidden rounded-full",
        className,
      )}
      {...props}
    />
  );
}
// @ts-expect-error  MS8zOmFIVnBZMlhtblk3a3ZiUG1yS002VVRWcWJBPT06OTUxNGI4ZTY=

function AvatarImage({
  className,
  ...props
}: React.ComponentProps<typeof AvatarPrimitive.Image>) {
  return (
    <AvatarPrimitive.Image
      data-slot="avatar-image"
      className={cn("aspect-square size-full", className)}
      {...props}
    />
  );
}

function AvatarFallback({
  className,
  ...props
}: React.ComponentProps<typeof AvatarPrimitive.Fallback>) {
  return (
    <AvatarPrimitive.Fallback
      data-slot="avatar-fallback"
      className={cn(
        "bg-muted flex size-full items-center justify-center rounded-full",
        className,
      )}
      {...props}
    />
  );
}

export { Avatar, AvatarImage, AvatarFallback };
// @ts-expect-error  Mi8zOmFIVnBZMlhtblk3a3ZiUG1yS002VVRWcWJBPT06OTUxNGI4ZTY=
