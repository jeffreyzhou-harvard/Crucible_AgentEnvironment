import type { ReactNode } from "react";

/**
 * Resizable chart container. The user drags the bottom-right handle to resize;
 * Recharts' ResponsiveContainer picks up the new size via its ResizeObserver.
 */
export function ChartBox({
  height = 220,
  minHeight = 140,
  children,
}: {
  height?: number;
  minHeight?: number;
  children: ReactNode;
}) {
  return (
    <div
      className="relative resize-y overflow-hidden rounded-md pb-1.5"
      style={{ height, minHeight, maxHeight: 640 }}
      title="Drag the bottom-right corner to resize"
    >
      {children}
      <div className="pointer-events-none absolute bottom-0.5 right-0.5 h-2.5 w-2.5 border-b-2 border-r-2 border-zinc-700" />
    </div>
  );
}
