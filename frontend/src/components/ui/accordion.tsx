import { useState } from "react";
import { cn } from "../../lib/utils";

export interface QA {
  q: string;
  a: string;
}

export function Accordion({ items, tone = "dark" }: { items: QA[]; tone?: "dark" | "light" }) {
  const [open, setOpen] = useState<number | null>(0);
  const light = tone === "light";
  return (
    <div
      className={cn(
        "divide-y overflow-hidden rounded-xl border",
        light ? "divide-zinc-200 border-zinc-200 bg-white" : "divide-zinc-800 border-zinc-800",
      )}
    >
      {items.map((it, i) => {
        const isOpen = open === i;
        return (
          <div key={i}>
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : i)}
              className={cn(
                "flex w-full items-center justify-between gap-4 px-4 py-3.5 text-left text-sm font-medium",
                light ? "text-zinc-800 hover:bg-zinc-50" : "text-zinc-200 hover:bg-zinc-900/50",
              )}
            >
              <span>{it.q}</span>
              <span
                className={cn(
                  "text-lg leading-none transition-transform",
                  light ? "text-zinc-400" : "text-zinc-500",
                  isOpen && "rotate-45",
                )}
              >
                +
              </span>
            </button>
            {isOpen && (
              <div
                className={cn(
                  "px-4 pb-4 text-sm leading-relaxed",
                  light ? "text-zinc-600" : "text-zinc-400",
                )}
              >
                {it.a}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
