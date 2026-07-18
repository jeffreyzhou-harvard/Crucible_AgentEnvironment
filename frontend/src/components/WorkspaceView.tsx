import { useTrace } from "../hooks/useTrace";
import type { StreamStatus } from "../types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { PlaneStrip } from "./PlaneStrip";
import { TerminalFeed } from "./TerminalFeed";

const STATUS_STYLE: Record<StreamStatus, { label: string; cls: string; dot: string }> = {
  idle: { label: "idle", cls: "border-zinc-700 text-zinc-400", dot: "bg-zinc-500" },
  connecting: { label: "connecting", cls: "border-sky-800 text-sky-300", dot: "bg-sky-400 animate-pulse" },
  open: { label: "running", cls: "border-emerald-800 text-emerald-300", dot: "bg-emerald-400 animate-pulse" },
  done: { label: "complete", cls: "border-emerald-800 text-emerald-300", dot: "bg-emerald-400" },
  error: { label: "stream error", cls: "border-red-800 text-red-300", dot: "bg-red-400" },
};

export function WorkspaceView({
  workspaceId,
  traceId,
  onReset,
}: {
  workspaceId: string;
  traceId: string;
  onReset: () => void;
}) {
  const { events, status } = useTrace(traceId);
  const s = STATUS_STYLE[status];

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge className={s.cls}>
            <span className={`h-2 w-2 rounded-full ${s.dot}`} />
            {s.label}
          </Badge>
          <span className="font-mono text-xs text-zinc-500">{workspaceId}</span>
          <span className="font-mono text-xs text-zinc-600">· {traceId}</span>
        </div>
        <Button variant="outline" onClick={onReset}>
          New run
        </Button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[260px_1fr] gap-4">
        <PlaneStrip events={events} />
        <TerminalFeed events={events} />
      </div>
    </div>
  );
}
