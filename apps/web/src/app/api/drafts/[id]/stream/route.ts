import { NextResponse, type NextRequest } from "next/server";

import { freshSent, nextEvents, sse, type Sent } from "@/lib/draft-stream";
import { authorize } from "@/server/auth/authorize";
import { deviceOf, draftError, drafts, UUID } from "@/server/drafts";

export const dynamic = "force-dynamic";

const TICK_MS = 600; // a part lands within a tick of the worker writing it; one worker read per tick (BLD-C039)
const IDLE_TICK_MS = 1_000; // between runs: only looking for the next one
const HEARTBEAT_MS = 15_000;
const MAX_OPEN_MS = 5 * 60_000; // the browser reconnects on its own

/**
 * GET /api/drafts/{id}/stream[?run={run_id}] — the draft as it builds, as server-sent events (A-API.draft-stream,
 * BLD-C075): per run `run`, `hidden`, one `part` per part as it lands, `receipt`, `done`. Owner only. With `run`,
 * that run is sent from its start even if it already finished (the client opens the stream after posting a
 * message); without it, the run still building, then every new one while the stream is open.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const id = (await params).id;
  const device = deviceOf(request);
  const asked = request.nextUrl.searchParams.get("run");
  let first;
  try {
    first = (await drafts.live(me, device, id, asked && UUID.test(asked) ? asked : null)).body;
  } catch (err) {
    return draftError(err); // ownership, before any byte is streamed
  }
  const encoder = new TextEncoder();
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    cancel() {
      cancelled = true;
    },
    async start(controller) {
      const send = (text: string) => controller.enqueue(encoder.encode(text));
      const opened = Date.now();
      let lastBeat = opened;
      let seen = first.latest?.id ?? null; // the newest run when the stream opened
      let sent: Sent | null =
        first.run && (asked || first.run.state === "running") ? freshSent(first.run.id) : null;
      let view = first;
      try {
        while (!cancelled && !request.signal.aborted && Date.now() - opened < MAX_OPEN_MS) {
          if (sent && view.run && view.run.id === sent.runId) {
            for (const e of nextEvents(view.run, view.parts, sent)) send(sse(e));
            if (sent.done) sent = null;
          }
          const latest = view.latest?.id ?? null;
          if (!sent && latest && latest !== seen) {
            seen = latest;
            sent = freshSent(latest);
          }
          if (Date.now() - lastBeat >= HEARTBEAT_MS) {
            lastBeat = Date.now();
            send(": keep-alive\n\n");
          }
          await new Promise((r) => setTimeout(r, sent ? TICK_MS : IDLE_TICK_MS));
          view = (await drafts.live(me, device, id, sent?.runId ?? null)).body;
          if (sent) seen = sent.runId;
        }
        if (!cancelled) send("event: end\ndata: {}\n\n");
      } catch {
        if (!cancelled) send('event: error\ndata: {"error":"stream_unavailable"}\n\n');
      } finally {
        if (!cancelled) controller.close();
      }
    },
  });
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-store, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
