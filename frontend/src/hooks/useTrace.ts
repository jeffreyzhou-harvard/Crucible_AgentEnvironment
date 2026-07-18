import { useEffect, useRef, useState } from "react";
import { traceStreamUrl } from "../lib/api";
import type { StreamStatus, TraceEvent } from "../types";

/**
 * Subscribe to a trace's live event stream over WebSocket.
 *
 * The backend replays the full history on connect, then streams live events until
 * `workspace.end`, so this hook works whether it connects before, during, or after
 * the run — no gaps, no duplicates.
 */
export function useTrace(traceId: string | null): {
  events: TraceEvent[];
  status: StreamStatus;
} {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const doneRef = useRef(false);

  useEffect(() => {
    if (!traceId) return;

    setEvents([]);
    setStatus("connecting");
    doneRef.current = false;

    const ws = new WebSocket(traceStreamUrl(traceId));

    ws.onopen = () => setStatus("open");
    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as TraceEvent;
      setEvents((prev) => [...prev, event]);
      if (event.kind === "workspace.end") {
        doneRef.current = true;
        setStatus("done");
      }
    };
    ws.onerror = () => {
      if (!doneRef.current) setStatus("error");
    };

    return () => ws.close();
  }, [traceId]);

  return { events, status };
}
