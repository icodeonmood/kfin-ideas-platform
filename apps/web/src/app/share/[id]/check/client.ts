/**
 * S-05's calls (A-API.drafts, A-API.files, A-API.ideas `similar`, A-API.team-up), as the browser makes them. Every
 * call answers `{ ok: true, body }` or `{ ok: false, status, error }` and never throws, so a part can say what went
 * wrong under itself (C-FIELD-MSG) and keep the rest working. No words are logged here (non-negotiable 3).
 *
 * Where each route lives while lanes land: sorting, fix, helpers, send and submit are lane C's (c/sort-submit, merged
 * here); the draft (`GET /drafts/:id`, parts, hidden details) is c/draft and c/hide; similar ideas and "Keep mine
 * separate" are c/similar; files and links are c/files; the merge request and team-up withdraw are lane F's.
 */
import type {
  ApiError,
  ConfigResponse,
  Draft,
  EditPageResponse,
  EditSaveResponse,
  FileItem,
  FixRemoved,
  FixRequest,
  FixResponse,
  HelpersRequest,
  HelpersResponse,
  HiddenDetail,
  IdeaPatch,
  SendViewResponse,
  ShowReason,
  SimilarMatch,
  SortingPatch,
  SortingResponse,
  SubmitResponse,
  UploadConfig,
} from "@/lib/contracts";
import { IDEMPOTENCY_HEADER } from "@/lib/contracts/api";

export type Call<T> =
  { ok: true; status: number; body: T } | { ok: false; status: number; error: ApiError["error"] | null };

/** The draft as S-05 reads it: E-ENTITIES `Draft`, plus "Keep mine separate" (BLD-C095) when the route sends it. */
export type CheckDraft = Draft & { kept_separate?: boolean };

/** Lane F's `GET /drafts/:id/merge-request` (L-MERGE.request/4–8): the latest request and what Check it shows. */
export interface MergeState {
  id?: string;
  other_idea_id?: string;
  state: string;
  note?: string;
  lead?: { id: string; name: string; first_name?: string; initials?: string };
  lead_reason?: string;
  after: {
    state: string;
    line: string;
    label?: string;
    action?: { label: string; op?: string; to?: string } | null;
    can_submit?: boolean;
  } | null;
}

const enc = encodeURIComponent;

export const urls = {
  draft: (id: string) => `/api/drafts/${enc(id)}`,
  part: (id: string, part: "title" | "summary" | "often") => `/api/drafts/${enc(id)}/parts/${part}`,
  show: (id: string, hid: string) => `/api/drafts/${enc(id)}/hidden/${enc(hid)}/show`,
  hide: (id: string, hid: string) => `/api/drafts/${enc(id)}/hidden/${enc(hid)}/hide`,
  sorting: (id: string) => `/api/drafts/${enc(id)}/sorting`,
  fix: (id: string) => `/api/drafts/${enc(id)}/fix`,
  helpers: (id: string) => `/api/drafts/${enc(id)}/helpers`,
  send: (id: string) => `/api/drafts/${enc(id)}/send`,
  submit: (id: string) => `/api/drafts/${enc(id)}/submit`,
  merge: (id: string) => `/api/drafts/${enc(id)}/merge-request`,
  similar: (id: string) => `/api/ideas/${enc(id)}/similar`,
  keepSeparate: (id: string) => `/api/ideas/${enc(id)}/similar/keep-separate`,
  teamUp: (requestId: string) => `/api/team-up/${enc(requestId)}`,
  files: "/api/files",
  links: "/api/links",
  file: (fileId: string) => `/api/files/${enc(fileId)}`,
  fileHide: (fileId: string) => `/api/files/${enc(fileId)}/hide`,
  fileRetry: (fileId: string) => `/api/files/${enc(fileId)}/retry`,
  config: "/api/config",
  uploads: "/api/config/uploads",
  edit: (ideaId: string) => `/api/ideas/${enc(ideaId)}/edit`,
} as const;

/** Where a file or link belongs (A-API.files): a draft on Check it, a shared idea on the edit page (S-06B). */
export type ProofTarget = { draft_id: string } | { idea_id: string };

function errorOf(body: unknown): ApiError["error"] | null {
  if (!body || typeof body !== "object") return null;
  const e = (body as { error?: unknown }).error;
  if (e && typeof e === "object" && typeof (e as { code?: unknown }).code === "string") {
    return e as ApiError["error"];
  }
  // The worker's bare shape, `{ error: "code" }`.
  if (typeof e === "string") return { code: e as ApiError["error"]["code"], message: "" };
  return null;
}

export async function call<T>(
  url: string,
  init: { method?: string; body?: unknown; form?: FormData; headers?: Record<string, string> } = {},
): Promise<Call<T>> {
  const headers: Record<string, string> = { Accept: "application/json", ...(init.headers ?? {}) };
  let body: BodyInit | undefined;
  if (init.form) body = init.form;
  else if (init.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body);
  }
  let res: Response;
  try {
    res = await fetch(url, { method: init.method ?? "GET", headers, body, cache: "no-store" });
  } catch {
    return { ok: false, status: 0, error: null };
  }
  let parsed: unknown = null;
  if (res.status !== 204) parsed = await res.json().catch(() => null);
  if (res.ok) return { ok: true, status: res.status, body: parsed as T };
  return { ok: false, status: res.status, error: errorOf(parsed) };
}

export const api = {
  draft: (id: string) => call<CheckDraft>(urls.draft(id)),
  step: (id: string, step: string) => call<unknown>(urls.draft(id), { method: "PATCH", body: { step } }),
  part: (id: string, part: "title" | "summary" | "often", value: string) =>
    call<unknown>(urls.part(id, part), { method: "PATCH", body: { value } }),
  showHidden: (id: string, hid: string, reason: ShowReason) =>
    call<HiddenDetail>(urls.show(id, hid), { method: "POST", body: { reason } }),
  hideAgain: (id: string, hid: string) => call<HiddenDetail>(urls.hide(id, hid), { method: "POST" }),
  config: () => call<ConfigResponse>(urls.config),
  uploads: () => call<UploadConfig>(urls.uploads),
  sorting: (id: string) => call<SortingResponse>(urls.sorting(id)),
  patchSorting: (id: string, patch: SortingPatch) =>
    call<SortingResponse>(urls.sorting(id), { method: "PATCH", body: patch }),
  putFix: (id: string, fix: FixRequest) => call<FixResponse>(urls.fix(id), { method: "PUT", body: fix }),
  removeFix: (id: string) => call<FixRemoved>(urls.fix(id), { method: "DELETE" }),
  putHelpers: (id: string, helpers: HelpersRequest) =>
    call<HelpersResponse>(urls.helpers(id), { method: "PUT", body: helpers }),
  send: (id: string) => call<SendViewResponse>(urls.send(id)),
  submit: (id: string, declarationVersion: string, key: string) =>
    call<SubmitResponse>(urls.submit(id), {
      method: "POST",
      body: { declaration_version: declarationVersion },
      headers: { [IDEMPOTENCY_HEADER]: key },
    }),
  similar: (id: string) => call<SimilarMatch[]>(urls.similar(id)),
  keepSeparate: (id: string, on: boolean) =>
    call<{ kept_separate: boolean }>(urls.keepSeparate(id), { method: "POST", body: { on } }),
  merge: (id: string) => call<MergeState>(urls.merge(id)),
  withdrawMerge: (id: string) => call<MergeState>(urls.merge(id), { method: "DELETE" }),
  withdrawTeamUp: (requestId: string) => call<unknown>(urls.teamUp(requestId), { method: "DELETE" }),
  upload: (to: string | ProofTarget, file: File) => {
    const form = new FormData();
    const [key, id] = Object.entries(typeof to === "string" ? { draft_id: to } : to)[0]!;
    form.append(key, id);
    form.append("file", file, file.name);
    return call<FileItem>(urls.files, { method: "POST", form });
  },
  link: (to: string | ProofTarget, url: string) =>
    call<FileItem>(urls.links, {
      method: "POST",
      body: { url, ...(typeof to === "string" ? { draft_id: to } : to) },
    }),
  file: (fileId: string) => call<FileItem>(urls.file(fileId)),
  hideFile: (fileId: string) => call<FileItem>(urls.fileHide(fileId), { method: "POST" }),
  retryFile: (fileId: string) => call<FileItem>(urls.fileRetry(fileId), { method: "POST" }),
  removeFile: (fileId: string) => call<unknown>(urls.file(fileId), { method: "DELETE" }),
  /** S-06B: the edit page (`GET /ideas/:id/edit`) and its Save (A-API `PATCH /ideas/:id`, served at `/edit`). */
  editPage: (ideaId: string) => call<EditPageResponse>(urls.edit(ideaId)),
  saveEdit: (ideaId: string, patch: IdeaPatch & { declaration_version: string }) =>
    call<EditSaveResponse>(urls.edit(ideaId), { method: "PATCH", body: patch }),
};

/** One key per send attempt of this draft on this page, so a retry never creates two ideas (A-API.conventions/3). */
export function sendKey(draftId: string): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
  return `s05:${draftId}:${rand}`;
}
