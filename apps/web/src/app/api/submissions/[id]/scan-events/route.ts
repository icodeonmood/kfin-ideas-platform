import { NextResponse, type NextRequest } from "next/server";

import { authorize } from "@/server/auth/authorize";
import { asResponse } from "@/server/http";
import { scanStatus, scanVersion } from "@/server/scan";

export const dynamic = "force-dynamic";

const TICK_MS = 1_000;
const HEARTBEAT_MS = 15_000;
const MAX_OPEN_MS = 5 * 60_000; // the browser reconnects on its own; no stream lives for ever
const MOVING = new Set(["queued", "running", "waiting"]); // as the poller: after these, only the person acts

/**
 * GET /api/submissions/{id}/scan-events — live scan progress as server-sent events (§8, week 3; replaces polling
 * while `scan.live` is on). The owner only, like scan-status. Each `status` event carries the same view as
 * scan-status, sent when the scan or the idea's stage moves. The stream ends once the scan has settled.
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const me = await authorize("submit");
  if (me instanceof NextResponse) return me;
  const id = (await params).id;
  let first: Record<string, unknown>;
  try {
    first = await scanStatus(me, id); // ownership and the first view, before any byte is streamed
  } catch (err) {
    return asResponse(err);
  }
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (text: string) => controller.enqueue(encoder.encode(text));
      const status = (view: Record<string, unknown>) =>
        send(`event: status\ndata: ${JSON.stringify(view)}\n\n`);
      const opened = Date.now();
      let lastBeat = opened;
      let version = await scanVersion(id).catch(() => null);
      status(first);
      try {
        while (!request.signal.aborted && Date.now() - opened < MAX_OPEN_MS) {
          if (!MOVING.has(String(first.state))) break; // settled: what changes next is the person's own doing
          await new Promise((r) => setTimeout(r, TICK_MS));
          const next = await scanVersion(id).catch(() => null);
          if (next && next !== version) {
            version = next;
            first = await scanStatus(me, id);
            status(first);
          } else if (Date.now() - lastBeat >= HEARTBEAT_MS) {
            lastBeat = Date.now();
            send(": keep-alive\n\n");
          }
        }
        send("event: end\ndata: {}\n\n");
      } catch {
        send('event: error\ndata: {"error":"scan_unavailable"}\n\n');
      } finally {
        controller.close();
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
