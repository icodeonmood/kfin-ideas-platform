/**
 * Files and links, web side (A-API.files, L-HIDE.files, C-FILE; lane C, BLD-C105 to BLD-C109). The worker does the
 * work: it stores a file in quarantine, scans it, reads its text and hides customers' details (L-HIDE), and it alone
 * decides who sees and opens a file (DEC-107: a file with a customer detail opens only for the person who added
 * it, the review desk and the Ones Committee). These handlers check the session, pass the signed-in person on as
 * `user_id`, and hand back the worker's FileItem or its error in the pack's shape, `{ error: { code, message } }`.
 *
 * Routes: `POST /api/files` (multipart: `file`, one of `draft_id`, `idea_id`, `answer_id`, and `for: "conversation"`
 * beside `idea_id` for the conversation's "+", BLD-C216), `POST /api/links`,
 * `GET /api/files/:id` (polling), `GET /api/files/:id/view` (the checked copy), `GET /api/config/uploads`,
 * `POST /api/files/:id/retry`, `DELETE /api/files/:id`, and `POST /api/files/:id/hide` ("Hide it for me", which
 * answers `not_available` while `files.blackout` is off; black-out is not built, DEC-107).
 * Errors never carry a file name, a link or anything read from a file (non-negotiable 3).
 */
import { NextResponse } from "next/server";

import { BANNERS } from "@/lib/killswitch-routes";

import type { CurrentUser } from "./auth/current";
import { isOn, switchStates } from "./killswitch";
import { workerFetch } from "./worker";

const NO_STORE = { "Cache-Control": "no-store" } as const;
const TARGETS = ["draft_id", "idea_id", "answer_id"] as const;
/** A multipart body carries the file and a few short fields; this much room is left for them. */
export const FORM_SLACK_BYTES = 64 * 1024;
/** One file up to the configured limit, and never past the proxy's body ceiling (next.config.ts, BLD-C108). */
export const MAX_LIMIT_MB = 25;

/** F-COPY's failure line when the worker cannot be reached (`C-FILE.row`: one failed file never blocks the others). */
export const UPLOAD_FAILED = "Didn’t upload. Your other files are fine.";
const NOT_REACHED = {
  code: "files_unavailable",
  message: "That didn’t go through. Try again in a moment.",
} as const;

export type UploadConfig = { limit_mb: number; types: string[]; help_text: string };

function errorJson(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
  return NextResponse.json({ error: { ...extra, code, message } }, { status, headers: NO_STORE });
}

/** The worker's answer as it is (JSON, or 204), or the pack's failure shape when it cannot be reached. */
async function forward(path: string, init: RequestInit = {}): Promise<NextResponse> {
  let res: Response;
  let text: string;
  try {
    res = await workerFetch(path, init);
    text = await res.text();
  } catch {
    return errorJson(502, NOT_REACHED.code, NOT_REACHED.message);
  }
  if (res.status === 204) return new NextResponse(null, { status: 204, headers: NO_STORE });
  try {
    return NextResponse.json(JSON.parse(text) as unknown, { status: res.status, headers: NO_STORE });
  } catch {
    return errorJson(502, NOT_REACHED.code, NOT_REACHED.message);
  }
}

const who = (me: CurrentUser) => `user_id=${encodeURIComponent(me.id)}`;
const fileId = (id: string) => encodeURIComponent(id);

/** `GET /api/config/uploads`: the one limit, the type list and the help line written from them. */
export async function uploadConfig(): Promise<UploadConfig> {
  const res = await workerFetch("/internal/files/config");
  if (!res.ok) throw new Error(`worker answered ${res.status}`);
  return (await res.json()) as UploadConfig;
}

export function tooBig(limitMb: number): NextResponse {
  return errorJson(413, "too_big", `Too big. Files can be up to ${limitMb} MB.`, { limit_mb: limitMb });
}

/**
 * `POST /api/files`. A body plainly over the limit is refused from its Content-Length before it is read; the worker
 * checks the file itself again (size, a password, the real type) before anything is stored.
 */
export async function addFile(me: CurrentUser, request: Request): Promise<NextResponse> {
  let config: UploadConfig;
  try {
    config = await uploadConfig();
  } catch {
    return errorJson(502, NOT_REACHED.code, NOT_REACHED.message);
  }
  const limitMb = Math.min(config.limit_mb, MAX_LIMIT_MB);
  const header = request.headers.get("content-length");
  if (header === null) return errorJson(411, "length_required", UPLOAD_FAILED); // no chunked bodies
  if (Number(header) > limitMb * 1024 * 1024 + FORM_SLACK_BYTES) return tooBig(limitMb);
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!form || !(file instanceof File))
    return errorJson(400, "file_required", UPLOAD_FAILED, { field: "file" });
  if (file.size > limitMb * 1024 * 1024) return tooBig(limitMb);
  const out = new FormData();
  out.set("user_id", me.id);
  for (const key of TARGETS) {
    const value = form.get(key);
    if (typeof value === "string" && value) out.set(key, value.slice(0, 100));
  }
  // `for: "conversation"` beside `idea_id`: the "+" in the conversation's box (DEC-124, BLD-C216). The worker takes
  // only that value, and only with an idea (422 otherwise), and stores it as the file's purpose.
  const purpose = form.get("for");
  if (typeof purpose === "string" && purpose) out.set("for", purpose.slice(0, 40));
  out.set("file", file, file.name.slice(-255) || "file");
  return forward("/internal/files", { method: "POST", body: out, signal: AbortSignal.timeout(120_000) });
}

/** `POST /api/links` `{ url, draft_id | idea_id | answer_id }`. The address is never fetched (BLD-E001). */
export async function addLink(me: CurrentUser, body: Record<string, unknown>): Promise<NextResponse> {
  const out: Record<string, unknown> = { user_id: me.id };
  if (typeof body.url === "string") out.url = body.url.slice(0, 4000);
  for (const key of TARGETS) if (typeof body[key] === "string") out[key] = String(body[key]).slice(0, 100);
  return forward("/internal/links", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(out),
  });
}

/** `GET /api/files/:id`: the FileItem, for the screens to follow the check. */
export const fileItem = (me: CurrentUser, id: string) => forward(`/internal/files/${fileId(id)}?${who(me)}`);

/** `POST /api/files/:id/retry` ("Try again"). */
export const retryFile = (me: CurrentUser, id: string) =>
  forward(`/internal/files/${fileId(id)}/retry?${who(me)}`, { method: "POST" });

/** `DELETE /api/files/:id` ("Remove", "Remove file"): the person who added it, in any state. */
export const removeFile = (me: CurrentUser, id: string) =>
  forward(`/internal/files/${fileId(id)}?${who(me)}`, { method: "DELETE" });

/** `POST /api/files/:id/hide` ("Hide it for me"). Black-out is not built (DEC-107): while `files.blackout` is off this
 * answers `not_available` with the switch's own notice, and the worker answers the same while it is on. */
export async function hideFile(me: CurrentUser, id: string): Promise<NextResponse> {
  let on = false;
  try {
    on = isOn(await switchStates(), "files.blackout");
  } catch {
    on = false;
  }
  if (!on) return errorJson(503, "not_available", BANNERS["files.blackout"]);
  return forward(`/internal/files/${fileId(id)}/hide?${who(me)}`, { method: "POST" });
}

/** Types a browser may show in place: images and PDFs, for C-FILE.view's viewer. Everything else downloads. */
const INLINE = new Set(["application/pdf", "image/png", "image/jpeg"]);

/** The headers for a file served from this origin: never sniffed; never run as a page (a sandbox for everything
 * but a PDF, whose built-in viewer a sandbox would block; its type is read from its bytes, never from its name);
 * shown in place only for images and PDFs; never cached. */
export function viewHeaders(mime: string, name: string): Record<string, string> {
  const type = mime || "application/octet-stream";
  const ascii = name.replace(/[^A-Za-z0-9._ -]/g, "_").slice(0, 120) || "file";
  const disposition = INLINE.has(type) ? "inline" : "attachment";
  const headers: Record<string, string> = {
    "Content-Type": type,
    "Content-Disposition": `${disposition}; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(name)}`,
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
    "Referrer-Policy": "no-referrer",
  };
  if (type !== "application/pdf") headers["Content-Security-Policy"] = "sandbox; default-src 'none'";
  return headers;
}

/** `GET /api/files/:id/view`: the checked copy, streamed, to the people the worker allows. Anyone else, and any file
 * not checked yet, gets the worker's 404 or 403. Every opening is audited by the worker. */
export async function viewFile(me: CurrentUser, id: string): Promise<NextResponse> {
  let res: Response;
  try {
    // The timer also bounds the body stream, so allow for a 25 MB file on a slow link.
    res = await workerFetch(`/internal/files/${fileId(id)}/content?${who(me)}`, {
      signal: AbortSignal.timeout(300_000),
    });
  } catch {
    return errorJson(502, NOT_REACHED.code, NOT_REACHED.message);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as unknown;
    if (body && typeof body === "object" && "error" in body)
      return NextResponse.json(body, { status: res.status, headers: NO_STORE });
    return errorJson(502, NOT_REACHED.code, NOT_REACHED.message);
  }
  let name = "file";
  try {
    name = decodeURIComponent(res.headers.get("x-file-name") ?? "file") || "file";
  } catch {
    name = "file";
  }
  return new NextResponse(res.body, {
    status: 200,
    headers: viewHeaders(res.headers.get("content-type") ?? "", name),
  });
}
