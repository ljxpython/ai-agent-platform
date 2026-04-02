import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-[color,box-shadow,background-color,opacity] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/40 focus-visible:ring-[3px] focus-visible:ring-offset-2",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-sm hover:opacity-90",
        primary: "bg-primary text-primary-foreground shadow-sm hover:opacity-90",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:opacity-90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:opacity-90",
        ghost: "border border-transparent hover:bg-accent hover:text-accent-foreground",
        link: "h-auto rounded-none px-0 text-primary underline-offset-4 hover:underline",
        brand:
          "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm hover:opacity-90",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-sm",
        md: "h-10 px-4 py-2",
        lg: "h-11 rounded-md px-6",
        icon: "size-9 rounded-full p-0",
      },
    },
    defaultVariants: {
      variant: "ghost",
      size: "default",
    },
  },
);

export type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { buttonVariants };
