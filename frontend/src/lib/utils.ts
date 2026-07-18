import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// The shadcn `cn` helper: merge conditional class lists, resolving Tailwind conflicts.
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
