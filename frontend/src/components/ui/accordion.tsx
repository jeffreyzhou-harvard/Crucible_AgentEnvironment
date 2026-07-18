import { useState } from "react";
import { cn } from "../../lib/utils";

export interface QA {
  q: string;
  a: string;
}

export function Accordion({ items }: { items: QA[] }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-zinc-800 overflow-hidden rounded-xl border border-zinc-800">
      {items.map((it, i) => {
        const isOpen = open === i;
        return (
          <div key={i}>
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : i)}
              className="flex w-full items-center justify-between gap-4 px-4 py-3.5 text-left text-sm font-medium text-zinc-200 hover:bg-zinc-900/50"
            >
              <span>{it.q}</span>
              <span
                className={cn(
                  "text-lg leading-none text-zinc-500 transition-transform",
                  isOpen && "rotate-45",
                )}
              >
                +
              </span>
            </button>
            {isOpen && <div className="px-4 pb-4 text-sm leading-relaxed text-zinc-400">{it.a}</div>}
          </div>
        );
      })}
    </div>
  );
}
