/**
 * The draft as Tell it talks to it (S-04, S-04B; A-API.drafts, L-DRAFT.autosave; BLD-C122). One place for the
 * device headers, the refusal shape, retries and the offline outbox.
 *
 * Every POST /api/drafts/:id/messages carries a `client_id` (as the Idempotency-Key the route turns into it), made
 * once per message and reused on every retry and every replay: a retried voice note whose answer was lost then comes
 * back as the stored message with its English copy, instead of a second message without it. A message that cannot be
 * sent waits in the outbox on this device with its own `client_id` and the time it was written (`at`), and is sent
 * again, in order, once the browser is back online (L-DRAFT.autosave/7). Nothing here logs words.
 */
import {
  IDEMPOTENCY_HEADER,
  type AddMessageResponse,
  type CreateDraftResponse,
  type Draft,
  type DraftListItem,
  type DraftPartKey,
  type HiddenDetail,
  type MessageVia,
  type PartResponse,
  type ShowReason,
} from "@/lib/contracts";

export type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export const DEVICE_ID_KEY = "1pc.device-id";
const OUTBOX_PREFIX = "1pc.outbox.";
const OUTBOX_KEY = (draftId: string) => `${OUTBOX_PREFIX}${draftId}`;
const RETRY_DELAYS_MS = [400, 1200, 3000] as const;
const TIMEOUT_MS = 15_000;

/** A refusal in A-API.conventions/2 shape, or `offline` when nothing answered. `message` is ready to show. */
export class DraftError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly text: string | null,
    readonly extra: Record<string, unknown> = {},
  ) {
    super(code);
  }
  get offline(): boolean {
    return this.status === 0;
  }
}

/** One message waiting to be sent: its id for the server and the moment it was written. */
export type Outgoing = {
  clientId: string;
  text: string;
  via: MessageVia;
  /** A voice note's stream (DEC-108): the server takes its words and English copy from it. */
  streamId?: string;
  /** Set when it was queued offline (L-DRAFT.autosave/7); a first try does not send it. */
  at?: string;
};

/** A finished voice note waiting in the box after what was typed (BLD-C150). `prefix` is the box as it was when the
 * note joined it; null once the note is already the draft's first message (S-04, an empty box). */
export type HeldNote = { streamId: string; text: string; textEn: string | null; prefix: string | null };

/** Where the note's words start in the box: after the typed words as they were, or, if those were changed, where
 * the note's own words end the box; -1 when neither holds. */
export function noteStart(box: string, note: HeldNote): number {
  if (note.prefix === null) return -1;
  if (box.startsWith(note.prefix)) return note.prefix.length;
  const end = box.trimEnd();
  return end.endsWith(note.text) ? end.length - note.text.length : -1;
}

/**
 * BLD-C150: what is typed is sent first as its own typed message, then the voice note as its own message (via
 * `voice` with its `stream_id`, so the server keeps its English copy, DEC-108), each with its own client_id. A box
 * that cannot be split (both parts changed) goes as one message with the note's stream: the server keeps the
 * person's changed words without the English copy (L-DRAFT.voice).
 */
export function messagesFor(box: string, note: HeldNote | null): Outgoing[] {
  const text = box.trim();
  if (!text) return [];
  if (!note || note.prefix === null) return [{ clientId: newClientId(), text, via: "typed" }];
  const at = noteStart(box, note);
  if (at < 0) return [{ clientId: newClientId(), text, via: "voice", streamId: note.streamId }];
  const typed = box.slice(0, at).trim();
  const spoken = box.slice(at).trim();
  const out: Outgoing[] = [];
  if (typed) out.push({ clientId: newClientId(), text: typed, via: "typed" });
  if (spoken) out.push({ clientId: newClientId(), text: spoken, via: "voice", streamId: note.streamId });
  return out;
}

/** Sign-out: no one's waiting words stay on a shared device (the outbox holds raw text; S-04.rules/4 keeps the
 * draft on the server, not here). */
export function clearOutboxes(store: Store | null = defaultStore()): void {
  try {
    if (!store || !("length" in store) || !("key" in store)) return;
    const s = store as unknown as Storage;
    const keys: string[] = [];
    for (let i = 0; i < s.length; i += 1) {
      const k = s.key(i);
      if (k && k.startsWith(OUTBOX_PREFIX)) keys.push(k);
    }
    for (const k of keys) s.removeItem(k);
  } catch {
    // storage blocked: nothing was kept there
  }
}

export function newClientId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  // Older browsers: 122 random bits in UUID form, still opaque and unique per message.
  const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

function defaultStore(): Store | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null; // storage blocked: the device id changes per visit and the outbox lives in memory only
  }
}

/** Transient: the same request may be sent again (lost connection, a busy server, a timeout). */
function retryable(status: number): boolean {
  return (
    status === 0 ||
    status === 408 ||
    status === 429 ||
    status === 500 ||
    status === 502 ||
    status === 503 ||
    status === 504
  );
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export type DraftClientOptions = {
  fetch?: typeof fetch;
  store?: Store | null;
  retryDelaysMs?: readonly number[];
};

export class DraftClient {
  private readonly fetchImpl: typeof fetch;
  private readonly store: Store | null;
  private readonly delays: readonly number[];
  private memoryOutbox = new Map<string, Outgoing[]>();
  private deviceId: string | null = null;

  constructor(options: DraftClientOptions = {}) {
    this.fetchImpl = options.fetch ?? ((...a: Parameters<typeof fetch>) => fetch(...a));
    this.store = options.store === undefined ? defaultStore() : options.store;
    this.delays = options.retryDelaysMs ?? RETRY_DELAYS_MS;
  }

  /** This browser's opaque id, so the server can say "on this laptop" and keep one editor (L-DRAFT.autosave/4–5). */
  device(): string {
    if (this.deviceId) return this.deviceId;
    let id: string | null = null;
    try {
      id = this.store?.getItem(DEVICE_ID_KEY) ?? null;
    } catch {
      id = null;
    }
    if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
      id = newClientId().replace(/-/g, "");
      try {
        this.store?.setItem(DEVICE_ID_KEY, id);
      } catch {
        // kept for this visit only
      }
    }
    this.deviceId = id;
    return id;
  }

  /** A fetch that sends the device id; use it for the voice hook too. */
  readonly fetch = (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
    const headers = new Headers(init.headers);
    headers.set("X-Device-Id", this.device());
    return this.fetchImpl(input, { ...init, headers });
  };

  private async once<T>(path: string, init: RequestInit, key?: string): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body) headers.set("Content-Type", "application/json");
    if (key) headers.set(IDEMPOTENCY_HEADER, key);
    let res: Response;
    try {
      res = await this.fetch(path, {
        ...init,
        headers,
        cache: "no-store",
        signal: init.signal ?? AbortSignal.timeout(TIMEOUT_MS),
      });
    } catch {
      throw new DraftError(0, "offline", null);
    }
    if (res.status === 204) return undefined as T;
    const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) {
      const err = (body.error && typeof body.error === "object" ? body.error : {}) as Record<string, unknown>;
      const { code, message, ...extra } = err;
      throw new DraftError(
        res.status,
        typeof code === "string" ? code : "save_failed",
        typeof message === "string" ? message : null,
        extra,
      );
    }
    return body as T;
  }

  /** Sends again, with the same body and key, while the failure is transient; then gives up with the last error. */
  private async withRetries<T>(path: string, init: RequestInit, key?: string): Promise<T> {
    let last: DraftError | null = null;
    for (let attempt = 0; attempt <= this.delays.length; attempt += 1) {
      if (attempt > 0) await sleep(this.delays[attempt - 1]!);
      try {
        return await this.once<T>(path, init, key);
      } catch (err) {
        if (!(err instanceof DraftError) || !retryable(err.status)) throw err;
        last = err;
        if (typeof navigator !== "undefined" && navigator.onLine === false) break; // offline: the outbox takes it
      }
    }
    throw last ?? new DraftError(0, "offline", null);
  }

  get(id: string, open = false): Promise<Draft> {
    return this.once<Draft>(`/api/drafts/${encodeURIComponent(id)}${open ? "?open=1" : ""}`, {});
  }

  async recent(): Promise<DraftListItem[]> {
    const body = await this.once<{ items?: DraftListItem[] }>("/api/drafts?recent=1", {});
    return Array.isArray(body?.items) ? body.items.filter((d) => !d.archived) : [];
  }

  /** POST /api/drafts: the draft, on the first pause in typing (`text`) or before the first voice note (none). The
   * key is made once per draft by the caller, so a retry never makes a second draft. */
  create(key: string, text?: string): Promise<CreateDraftResponse> {
    return this.withRetries(
      "/api/drafts",
      { method: "POST", body: JSON.stringify({ channel: "web", ...(text ? { text, via: "typed" } : {}) }) },
      key,
    );
  }

  /** POST /api/drafts/:id/messages with the message's own client_id, on every try. */
  addMessage(draftId: string, m: Outgoing): Promise<AddMessageResponse> {
    const body = {
      text: m.text,
      via: m.via,
      client_id: m.clientId,
      ...(m.streamId ? { stream_id: m.streamId } : {}),
      ...(m.at ? { at: m.at } : {}),
    };
    return this.withRetries(
      `/api/drafts/${encodeURIComponent(draftId)}/messages`,
      { method: "POST", body: JSON.stringify(body) },
      m.clientId,
    );
  }

  /** PATCH /api/drafts/:id/messages/:mid: the box autosaving, or "Edit" on a sent message. */
  editMessage(draftId: string, mid: string, text: string): Promise<AddMessageResponse> {
    return this.withRetries(
      `/api/drafts/${encodeURIComponent(draftId)}/messages/${encodeURIComponent(mid)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ text }),
      },
    );
  }

  /** PATCH /api/drafts/:id/parts/:part: the person's own value (pinned), or `{ pinned: false }`. */
  setPart(draftId: string, part: DraftPartKey | "summary", body: { value: unknown } | { pinned: false }) {
    return this.withRetries<PartResponse>(
      `/api/drafts/${encodeURIComponent(draftId)}/parts/${encodeURIComponent(part)}`,
      { method: "PATCH", body: JSON.stringify(body) },
    );
  }

  /** C-HIDDEN "Show it" with one of the three reasons, and "Hide it" (A-API.drafts, L-HIDE.rules/6). */
  showHidden(draftId: string, hid: string, reason: ShowReason): Promise<HiddenDetail> {
    return this.once(`/api/drafts/${encodeURIComponent(draftId)}/hidden/${encodeURIComponent(hid)}/show`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  }

  hideHidden(draftId: string, hid: string): Promise<HiddenDetail> {
    return this.once(`/api/drafts/${encodeURIComponent(draftId)}/hidden/${encodeURIComponent(hid)}/hide`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  }

  /** PATCH /api/drafts/:id `{ step }`. */
  saveStep(draftId: string, step: string): Promise<unknown> {
    return this.once(`/api/drafts/${encodeURIComponent(draftId)}`, {
      method: "PATCH",
      body: JSON.stringify({ step }),
    });
  }

  // ── the outbox ──────────────────────────────────────────────────────────────────────────────────────────────

  outbox(draftId: string): Outgoing[] {
    try {
      const raw = this.store?.getItem(OUTBOX_KEY(draftId));
      if (raw) {
        const list = JSON.parse(raw) as unknown;
        if (Array.isArray(list)) return list.filter(isOutgoing);
      }
    } catch {
      // unreadable: fall back to this visit's copy
    }
    return [...(this.memoryOutbox.get(draftId) ?? [])];
  }

  private writeOutbox(draftId: string, list: Outgoing[]): void {
    this.memoryOutbox.set(draftId, list);
    try {
      if (list.length) this.store?.setItem(OUTBOX_KEY(draftId), JSON.stringify(list));
      else this.store?.removeItem(OUTBOX_KEY(draftId));
    } catch {
      // kept in memory for this visit
    }
  }

  /** Keeps a message that could not be sent, with its client_id and the time it was written. */
  queue(draftId: string, m: Outgoing): Outgoing {
    const kept: Outgoing = { ...m, at: m.at ?? new Date().toISOString() };
    const list = this.outbox(draftId).filter((x) => x.clientId !== kept.clientId);
    this.writeOutbox(draftId, [...list, kept]);
    return kept;
  }

  /** Sends what waits, oldest first, each with its own client_id and `at`. Stops at the first that still cannot
   * go, keeping it and everything after it. A message refused for good (too long, an archived draft) leaves the
   * queue and comes back in `refused`, so the screen can put its words back in the box: nothing typed is lost. */
  async flush(
    draftId: string,
  ): Promise<{ sent: AddMessageResponse[]; refused: { message: Outgoing; error: DraftError }[] }> {
    const sent: AddMessageResponse[] = [];
    const refused: { message: Outgoing; error: DraftError }[] = [];
    for (const m of this.outbox(draftId)) {
      try {
        sent.push(await this.addMessage(draftId, m));
      } catch (err) {
        const e = err instanceof DraftError ? err : new DraftError(0, "offline", null);
        if (retryable(e.status)) break;
        refused.push({ message: m, error: e });
      }
      this.writeOutbox(
        draftId,
        this.outbox(draftId).filter((x) => x.clientId !== m.clientId),
      );
    }
    return { sent, refused };
  }
}

function isOutgoing(v: unknown): v is Outgoing {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  return typeof o.clientId === "string" && typeof o.text === "string" && typeof o.via === "string";
}
