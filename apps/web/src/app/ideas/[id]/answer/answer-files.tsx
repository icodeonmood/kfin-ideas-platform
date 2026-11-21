"use client";

/**
 * S-R3's "+" on an answer (BLD-B275; DEC-124, C-PROMPT.attach, C-FILE.row, L-QUESTIONS.answer/1). Built on lane C's
 * Check it rows (`rowView`, `settling`, `pollDelay`) and lane D's `FileList` and `FileRow`, with lane F's pattern for
 * S-08's box (`components/convo/attach.tsx`): upload, ask again until the file settles, remove, try again.
 *
 * - Each file goes to `POST /api/files` with the answer's id (`answerUploadForm`), never `for: "conversation"`: an
 *   answer's file is one of the idea's own (BLD-B274), so DEC-107's checks run unchanged (the virus scan, then the
 *   personal-details check).
 * - An upload needs the answer's row: `answerId` makes it once per question (an empty save creates it) and every pick
 *   waits for that one save.
 * - A row with a customer detail found (DEC-107) says who can open it and may still be sent: nothing here blocks Send.
 *   "Hide it for me" shows only while `files.blackout` is on, as on Check it.
 *
 * No words or names are logged here (non-negotiable 3).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { api, call, urls, type Call } from "@/app/share/[id]/check/client";
import { CHECK_COPY } from "@/app/share/[id]/check/copy";
import { POLL, pollDelay, rowView, settling, type ProofItem } from "@/app/share/[id]/check/model";
import { S08_COPY } from "@/components/convo/compose";
import { Button } from "@/components/ui/button";
import { FileList, FileRow } from "@/components/ui/file";
import type { FileItem, UploadConfig } from "@/lib/contracts";
import { answerUploadForm } from "@/lib/desk/answer-files";

/** The limit before `GET /api/config/uploads` answers: the web edge's own ceiling; the worker checks the real one. */
const LIMIT_BEFORE_CONFIG_MB = 25;
/** The worker's refusals that trying again would not change: its words go under the row. */
const REFUSED = [
  "type_not_allowed",
  "locked",
  "forbidden",
  "not_found",
  "set_closed",
  "answer_sent",
  "answer_in_progress",
];

export type AnswerRows = Record<string, ProofItem[]>;

/** `POST /api/files` for an answer (A-API.files): the answer's id and the file. */
export function uploadForAnswer(answerId: string, file: File): Promise<Call<FileItem>> {
  return call<FileItem>(urls.files, { method: "POST", form: answerUploadForm(answerId, file) });
}

export interface AnswerFiles {
  /** Each question's rows, by question id. */
  rows: AnswerRows;
  limitMb: number;
  /** Reads the one limit and type list (C-FILE.uploader/1), once. */
  loadConfig(): void;
  addFiles(qid: string, files: File[]): void;
  remove(qid: string, key: string): Promise<void>;
  retry(qid: string, key: string): Promise<void>;
  hide(qid: string, key: string): Promise<void>;
  /** Every upload still on its way has answered. */
  settle(): Promise<void>;
}

/**
 * The files of every answer on the screen. `answerId(qid)` gives the answer's id, saving the answer first when it has
 * no row yet; null when that save failed (the row offers "Try again").
 */
export function useAnswerFiles(
  initial: AnswerRows,
  answerId: (qid: string) => Promise<string | null>,
): AnswerFiles {
  const [rows, setRows] = useState<AnswerRows>(initial);
  const live = useRef<AnswerRows>(initial);
  const ensure = useRef(answerId);
  useEffect(() => {
    ensure.current = answerId;
  });
  const commit = useCallback((qid: string, fn: (list: ProofItem[]) => ProofItem[]) => {
    live.current = { ...live.current, [qid]: fn(live.current[qid] ?? []) };
    setRows(live.current);
  }, []);
  const replace = useCallback(
    (qid: string, key: string, next: Partial<ProofItem>) =>
      commit(qid, (list) => list.map((p) => (p.key === key ? { ...p, ...next } : p))),
    [commit],
  );
  const find = (qid: string, key: string) => (live.current[qid] ?? []).find((p) => p.key === key);
  const pending = useRef(new Map<string, Promise<unknown>>());
  const removedEarly = useRef(new Set<string>());
  const pollFails = useRef(new Map<string, number>());
  const [pollTick, setPollTick] = useState(0);
  const [config, setConfig] = useState<UploadConfig | null>(null);
  const asked = useRef(false);
  const limitMb = config?.limit_mb ?? LIMIT_BEFORE_CONFIG_MB;

  const loadConfig = useCallback(() => {
    if (asked.current) return;
    asked.current = true;
    void api.uploads().then((r) => {
      if (r.ok && r.body && typeof r.body.limit_mb === "number") setConfig(r.body);
      else asked.current = false; // ask again on the next pick
    });
  }, []);

  const upload = async (qid: string, key: string, file: File) => {
    replace(qid, key, { localState: "uploading", refusal: undefined, note: undefined });
    const posted = (async () => {
      const aid = await ensure.current(qid);
      return aid ? uploadForAnswer(aid, file) : null;
    })();
    pending.current.set(key, posted);
    const r = await posted;
    pending.current.delete(key);
    if (removedEarly.current.has(key)) {
      // Removed while it uploaded: what reached the server goes too.
      removedEarly.current.delete(key);
      if (r?.ok && r.body?.id) void api.removeFile(r.body.id);
      return;
    }
    if (r === null) {
      replace(qid, key, { localState: "upload_failed" });
      return;
    }
    if (r.ok) {
      replace(qid, key, {
        item: r.body,
        localState: undefined,
        refusal: undefined,
        name: r.body?.name || file.name,
      });
      return;
    }
    // A-API.files: the server's words for a refusal; anything else is "Didn't upload…" with Try again.
    const code = r.error?.code;
    const words = r.error?.message || undefined;
    if (r.status === 413 || code === "too_big") replace(qid, key, { localState: "too_big", refusal: words });
    else if (code && REFUSED.includes(code)) replace(qid, key, { localState: "refused", refusal: words });
    else replace(qid, key, { localState: "upload_failed" });
  };

  const addFiles = (qid: string, files: File[]) => {
    const stamp = Date.now();
    const fresh: ProofItem[] = files
      .filter((f) => !f.name.startsWith("."))
      .map((file, i) => ({
        key: `local-${stamp}-${i}-${file.name}`,
        item: null,
        local: file,
        name: file.name,
        localState: file.size > limitMb * 1024 * 1024 ? "too_big" : "uploading",
      }));
    if (!fresh.length) return;
    commit(qid, (list) => [...list, ...fresh]);
    for (const f of fresh) if (f.localState === "uploading" && f.local) void upload(qid, f.key, f.local);
  };

  const remove = async (qid: string, key: string) => {
    const p = find(qid, key);
    if (!p) return;
    if (p.item?.id) {
      replace(qid, key, { note: undefined });
      const r = await api.removeFile(p.item.id);
      if (r.ok || r.status === 404) {
        pollFails.current.delete(key);
        commit(qid, (list) => list.filter((x) => x.key !== key));
        return;
      }
      replace(qid, key, { note: (!r.ok && r.error?.message) || CHECK_COPY.failed });
      return;
    }
    if (p.localState === "uploading") removedEarly.current.add(key);
    commit(qid, (list) => list.filter((x) => x.key !== key));
  };

  const retry = async (qid: string, key: string) => {
    const p = find(qid, key);
    if (!p) return;
    if (p.stalled) {
      // Asking for its state had stopped: ask again, from the start.
      pollFails.current.delete(key);
      replace(qid, key, { stalled: false, note: undefined });
      return;
    }
    if (p.item?.id && !p.localState) {
      replace(qid, key, { item: { ...p.item, state: "uploading" } });
      const r = await api.retryFile(p.item.id);
      replace(qid, key, r.ok && r.body ? { item: r.body } : { item: { ...p.item, state: "upload_failed" } });
    } else if (p.local) await upload(qid, key, p.local);
  };

  // `files.blackout` off answers 503 `not_available`: the server's words under the row (C-FIELD-MSG), as on Check it.
  const hide = async (qid: string, key: string) => {
    const p = find(qid, key);
    if (!p?.item?.id) return;
    replace(qid, key, { note: undefined });
    const r = await api.hideFile(p.item.id);
    if (r.ok && r.body) replace(qid, key, { item: r.body });
    else replace(qid, key, { note: (!r.ok && r.error?.message) || CHECK_COPY.failed });
  };

  const settle = useCallback(async () => {
    await Promise.all(Array.from(pending.current.values()));
  }, []);

  // Files settle on the server (scan, then the personal-details check): ask again until they do, as Check it and
  // S-08 do (C-FILE.row, BLD-C139): every 2 s, longer after a failed ask, and "Try again" after five in a row.
  useEffect(() => {
    const moving = Object.entries(rows).flatMap(([qid, list]) =>
      list.filter(settling).map((p) => ({ qid, p })),
    );
    if (!moving.length) return;
    const worst = Math.max(0, ...moving.map(({ p }) => pollFails.current.get(p.key) ?? 0));
    const t = setTimeout(async () => {
      let again = false;
      for (const { qid, p } of moving) {
        if (!p.item?.id) continue;
        const r = await api.file(p.item.id);
        if (!(live.current[qid] ?? []).some((x) => x.key === p.key)) continue; // removed meanwhile
        if (r.ok && r.body) {
          pollFails.current.delete(p.key);
          replace(qid, p.key, { item: r.body });
          continue;
        }
        const fails = (pollFails.current.get(p.key) ?? 0) + 1;
        pollFails.current.set(p.key, fails);
        if (fails >= POLL.tries) replace(qid, p.key, { stalled: true });
        else again = true;
      }
      if (again) setPollTick((n) => n + 1);
    }, pollDelay(worst));
    return () => clearTimeout(t);
  }, [rows, pollTick, replace]);

  return { rows, limitMb, loadConfig, addFiles, remove, retry, hide, settle };
}

/**
 * One answer's rows under its box (C-FILE.row), in the list "Your files" (lane F's words). Check it's actions: "Try
 * again", "Hide it for me" while `files.blackout` is on, and "Remove", named "Remove {name}".
 */
export function AnswerFileRows({
  rows,
  limitMb,
  canHide,
  onRetry,
  onHide,
  onRemove,
}: {
  rows: readonly ProofItem[];
  limitMb: number;
  canHide: boolean;
  onRetry(key: string): void;
  onHide(key: string): void;
  onRemove(key: string): void;
}) {
  if (!rows.length) return null;
  const C = CHECK_COPY.proof;
  return (
    <div className="ans-files">
      <FileList label={S08_COPY.files}>
        {rows.map((p) => {
          const v = rowView(p, limitMb);
          const name = p.item?.name ?? p.name;
          return (
            <FileRow
              key={p.key}
              name={name}
              kind={v.kind}
              size={v.size}
              status={v.status}
              statusText={v.statusText}
              message={v.message}
            >
              {v.actions.includes("retry") ? (
                <Button variant="text-blue" onClick={() => onRetry(p.key)}>
                  {CHECK_COPY.retry}
                </Button>
              ) : null}
              {v.actions.includes("hide") && canHide ? (
                <Button variant="text-blue" onClick={() => onHide(p.key)}>
                  {C.hideForMe}
                </Button>
              ) : null}
              <Button variant="text" aria-label={C.removeOf(name)} onClick={() => onRemove(p.key)}>
                {C.remove}
              </Button>
            </FileRow>
          );
        })}
      </FileList>
    </div>
  );
}
