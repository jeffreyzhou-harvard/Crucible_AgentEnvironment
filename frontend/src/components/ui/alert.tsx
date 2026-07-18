import * as React from "react";
import { cn } from "../../lib/utils";

// shadcn-style Alert, destructive variant (see frontend-components skill patterns).
export function Alert({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "destructive" }) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-lg border px-3 py-2 text-sm",
        variant === "destructive"
          ? "border-red-900 bg-red-950/40 text-red-300"
          : "border-zinc-800 bg-zinc-900/60 text-zinc-300",
        className,
      )}
      {...props}
    />
  );
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn("mb-0.5 font-medium", className)} {...props} />;
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-xs opacity-90", className)} {...props} />;
}
