import * as React from "react";
import { cn } from "../../lib/utils";

type Variant = "default" | "outline" | "ghost";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const variants: Record<Variant, string> = {
  default: "bg-emerald-500 text-zinc-950 hover:bg-emerald-400",
  outline: "border border-zinc-700 text-zinc-200 hover:bg-zinc-800",
  ghost: "text-zinc-300 hover:bg-zinc-800",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
