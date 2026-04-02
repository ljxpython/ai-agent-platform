import * as React from "react";

import { cn } from "@/lib/utils/cn";

function Card({
  className,
  style,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "bg-card text-card-foreground border-border flex flex-col gap-6 rounded-[20px] border shadow-sm",
        className,
      )}
      style={{
        boxShadow: "var(--card-shadow)",
        ...style,
      }}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("flex flex-col gap-1.5 px-6 pt-6", className)}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("leading-none font-semibold", className)} {...props} />
  );
}

function CardDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-6 pb-6", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div className={cn("flex items-center px-6 pb-6", className)} {...props} />
  );
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
};
