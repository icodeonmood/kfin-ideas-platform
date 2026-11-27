"use client";

/**
 * S-08's "+" (DEC-124, walk item WF-01; BLD-F095): the files a message carries, for the readers who may attach
 * (`composer.can_attach`: the sharer, the review desk and the Ones Committee, BLD-F063, BLD-B270). Built from lane D's
 * shared pieces (`AttachButton`, C-FILE's `FilePicker`, `FileList`, `FileRow`) with the Home board's words
 * (`BOX_FILES_COPY`, C-PROMPT.attach) and Check it's row rules and polling (`rowView`, `settling`, `pollDelay`),
 * because lane C's `useBoxFiles` belongs to a draft.
 *
 * - Each file goes to `POST /api/files` with the idea's reference and `for: "conversation"` (lane C's BLD-C216), so
 *   DEC-107's checks run unchanged: the virus scan, then the personal-details check. Its row is asked again until it
 *   settles, as on Check it. "Remove {name}" deletes it (`DELETE /api/files/:id`).
 * - The message carries the ids of the rows on the server that have not failed; the worker takes the checked ones and
 *   refuses, in its own words, one still being checked (`file_not_checked`) or holding a customer detail
 *   (`file_has_detail`), so the box has one rule, the worker's (L-CONVO/7).
 * - A row with a customer detail says it can't be sent in the conversation and offers Remove (`fileHasDetail`), never
 *   Check it's line about who opens it.
 * - A link typed in the picker goes into the words as typed (`putLink`), never into a row and never fetched
 *   (non-negotiable 8); so the picker has no internal or external line.
 *
 * No words or names are logged here (non-negotiable 3).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { call, api, urls, type Call } from "@/app/share/[id]/check/client";
import { CHECK_COPY } from "@/app/share/[id]/check/copy";
import {
  POLL,
  pollDelay,
  rowView,
  settling,
  type ProofItem,
  type RowView,
} from "@/app/share/[id]/check/model";
import { BOX_FILES_COPY } from "@/app/share/box-files";
import { Button } from "@/components/ui/button";
import { FileList, FileRemove, FileRow } from "@/components/ui/file";
import { FilePicker, type LinkDraft } from "@/components/ui/file-picker";
import type { FileItem, UploadConfig } from "@/lib/contracts";

import { S08_COPY } from "./compose";

/** The limit before `GET /api/config/uploads` answers: the web edge's own ceiling; the worker checks the real one. */
const LIMIT_BEFORE_CONFIG_MB = 25;
/** A row whose file the message can never carry: its upload or its checks failed (C-FILE.row). */
const FAILED: ReadonlySet<string> = new Set(["upload_failed", "infected", "locked", "too_big"]);

/** `POST /api/files` for the conversation: the idea's reference and `for: "conversation"` (A-API.files, BLD-C216). */
export function uploadForConversation(ideaRef: string, file: File): Promise<Call<FileItem>> {
  const form = new FormData();
  form.append("idea_id", ideaRef);
  form.append("for", "conversation");
  form.append("file", file, file.name);
  return call<FileItem>(urls.files, { method: "POST", form });
}

/** A row the message carries: on the server, a file, and not failed. The worker decides on the rest (L-CONVO/7). */
export function sendable(p: ProofItem): boolean {
  const item = p.item;
  return Boolean(item?.id) && !p.localState && item?.kind === "file" && !FAILED.has(item.state);
}

/**
 * C-FILE.row in S-08's box: as Check it draws a row, with only "Try again" and Remove. A file with a customer detail
 * found can't be sent in the conversation (DEC-107, the worker's `file_has_detail`), so it says that, with Remove.
 */
export function convoRowView(p: ProofItem, limitMb: number): RowView {
  const v = rowView(p, limitMb);
  if (v.status === "found") {
    return {
      ...v,
      statusText: "",
      message: { kind: "warn", text: p.note || S08_COPY.fileHasDetail },
      actions: ["remove"],
    };
  }
  return { ...v, actions: v.actions.filter((a) => a === "retry" || a === "remove") };
}

export interface ConvoFiles {
  rows: ProofItem[];
  limitMb: number;
  /** The configured help line ("PDF, Word, … up to 25 MB each."), once read. */
  help: string | null;
  /** Reads the one limit, type list and help line (C-FILE.uploader/1), once. */
  loadConfig(): void;
  addFiles(files: File[]): void;
  /** True when nothing of the row is left on the server. */
  remove(key: string): Promise<boolean>;
  retry(key: string): Promise<void>;
  /** An upload is still on its way. */
  waiting(): boolean;
  /** Every upload still on its way has answered. */
  settle(): Promise<void>;
  /** The ids the message carries, as the rows stand now. */
  sendIds(): string[];
  /** After a message is sent: its files' rows leave the box. */
  clearSent(ids: readonly string[]): void;
}

/** The box's files for one idea's conversation. `onClosed` reads the conversation again when the idea closed under
 * an upload (409 `idea_closed`), so the box gives way to the line that says where to write. */
export function useConvoFiles(ideaRef: string, onClosed: () => void): ConvoFiles {
  const [rows, setRows] = useState<ProofItem[]>([]);
  // The rows as they stand, for a send that reads them straight after waiting for uploads (before any re-render).
  const live = useRef<ProofItem[]>([]);
  const target = useRef({ ideaRef, onClosed });
  useEffect(() => {
    target.current = { ideaRef, onClosed };
  });
  const commit = useCallback((fn: (list: ProofItem[]) => ProofItem[]) => {
    live.current = fn(live.current);
    setRows(live.current);
  }, []);
  const replace = useCallback(
    (key: string, next: Partial<ProofItem>) =>
      commit((list) => list.map((p) => (p.key === key ? { ...p, ...next } : p))),
    [commit],
  );
  const pending = useRef(new Map<string, Promise<Call<FileItem>>>());
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
      else asked.current = false; // ask again next time the picker opens
    });
  }, []);

  const upload = async (key: string, file: File) => {
    replace(key, { localState: "uploading", refusal: undefined, note: undefined });
    const posted = uploadForConversation(target.current.ideaRef, file);
    pending.current.set(key, posted);
    const r = await posted;
    pending.current.delete(key);
    if (removedEarly.current.has(key)) {
      // Removed while it uploaded: what reached the server goes too.
      removedEarly.current.delete(key);
      if (r.ok && r.body?.id) void api.removeFile(r.body.id);
      return;
    }
    if (r.ok) {
      replace(key, {
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
    if (r.status === 413 || code === "too_big") replace(key, { localState: "too_big", refusal: words });
    else if (code === "idea_closed") {
      replace(key, { localState: "refused", refusal: words });
      target.current.onClosed();
    } else if (code && ["type_not_allowed", "locked", "forbidden", "not_found"].includes(code)) {
      replace(key, { localState: "refused", refusal: words });
    } else replace(key, { localState: "upload_failed" });
  };

  const addFiles = (files: File[]) => {
    // A folder's own entries for the system (".DS_Store", ".git/…" and the like) are not the person's files: the
    // name, or any folder on its path, starts with "." (BLD-F109; the share box has the same check, BLD-C248).
    const stamp = Date.now();
    const fresh: ProofItem[] = files
      .filter((f) => !(f.webkitRelativePath || f.name).split("/").some((part) => part.startsWith(".")))
      .map((file, i) => ({
        key: `local-${stamp}-${i}-${file.name}`,
        item: null,
        local: file,
        name: file.name,
        localState: file.size > limitMb * 1024 * 1024 ? "too_big" : "uploading",
      }));
    if (!fresh.length) return;
    commit((list) => [...list, ...fresh]);
    for (const f of fresh) if (f.localState === "uploading" && f.local) void upload(f.key, f.local);
  };

  const remove = async (key: string): Promise<boolean> => {
    const p = live.current.find((x) => x.key === key);
    if (!p) return true;
    if (p.item?.id) {
      replace(key, { note: undefined });
      const r = await api.removeFile(p.item.id);
      if (r.ok || r.status === 404) {
        pollFails.current.delete(key);
        commit((list) => list.filter((x) => x.key !== key));
        return true;
      }
      replace(key, { note: (!r.ok && r.error?.message) || CHECK_COPY.failed });
      return false;
    }
    if (p.localState === "uploading") removedEarly.current.add(key);
    commit((list) => list.filter((x) => x.key !== key));
    return true;
  };

  const retry = async (key: string) => {
    const p = live.current.find((x) => x.key === key);
    if (!p) return;
    if (p.stalled) {
      // Asking for its state had stopped: ask again, from the start.
      pollFails.current.delete(key);
      replace(key, { stalled: false, note: undefined });
      return;
    }
    if (p.item?.id && !p.localState) {
      replace(key, { item: { ...p.item, state: "uploading" } });
      const r = await api.retryFile(p.item.id);
      replace(key, r.ok && r.body ? { item: r.body } : { item: { ...p.item, state: "upload_failed" } });
    } else if (p.local) await upload(key, p.local);
  };

  const waiting = useCallback(() => pending.current.size > 0, []);

  const settle = useCallback(async () => {
    await Promise.all(Array.from(pending.current.values()));
  }, []);

  const sendIds = useCallback(() => live.current.filter(sendable).map((p) => p.item!.id), []);

  const clearSent = useCallback(
    (ids: readonly string[]) => {
      if (!ids.length) return;
      commit((list) => list.filter((p) => !(p.item && ids.includes(p.item.id))));
    },
    [commit],
  );

  // Files settle on the server (scan, then the personal-details check): ask again until they do, as Check it does
  // (C-FILE.row, BLD-C139): every 2 s, longer after a failed ask, and "Try again" after five in a row.
  useEffect(() => {
    const moving = rows.filter(settling);
    if (!moving.length) return;
    const worst = Math.max(0, ...moving.map((p) => pollFails.current.get(p.key) ?? 0));
    const t = setTimeout(async () => {
      let again = false;
      for (const p of moving) {
        if (!p.item?.id) continue;
        const r = await api.file(p.item.id);
        if (!live.current.some((x) => x.key === p.key)) continue; // removed meanwhile
        if (r.ok && r.body) {
          pollFails.current.delete(p.key);
          replace(p.key, { item: r.body });
          continue;
        }
        const fails = (pollFails.current.get(p.key) ?? 0) + 1;
        pollFails.current.set(p.key, fails);
        if (fails >= POLL.tries) replace(p.key, { stalled: true });
        else again = true;
      }
      if (again) setPollTick((n) => n + 1);
    }, pollDelay(worst));
    return () => clearTimeout(t);
  }, [rows, pollTick, replace]);

  return {
    rows,
    limitMb,
    help: config?.help_text ?? null,
    loadConfig,
    addFiles,
    remove,
    retry,
    waiting,
    settle,
    sendIds,
    clearSent,
  };
}

/** The rows inside the box (C-FILE.row), each with "Remove {name}" (Home.md's words). */
export function ConvoFileRows({
  rows,
  limitMb,
  onRetry,
  onRemove,
}: {
  rows: ProofItem[];
  limitMb: number;
  onRetry(key: string): void;
  onRemove(key: string): void;
}) {
  if (!rows.length) return null;
  return (
    <div className="cv-files">
      <FileList label={S08_COPY.files} compact>
        {rows.map((p) => {
          const v = convoRowView(p, limitMb);
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
              waiting={v.waiting}
            >
              {v.actions.includes("retry") ? (
                <Button variant="text-blue" size="sm" onClick={() => onRetry(p.key)}>
                  {CHECK_COPY.retry}
                </Button>
              ) : null}
              <FileRemove label={BOX_FILES_COPY.removeOf(name)} onClick={() => onRemove(p.key)} />
            </FileRow>
          );
        })}
      </FileList>
    </div>
  );
}

/** The link field as the screen keeps it, so a picker drawn again (the width crossing 640px, BLD-F098) still holds
 * what was typed (BLD-F102). Lane D's picker's own type (BLD-D031). */
export { NO_LINK, type LinkDraft } from "@/components/ui/file-picker";

/**
 * The picker the "+" opens: lane D's shared C-FILE.uploader picker (BLD-D031), placed by `.cv-pick`. A link goes into
 * the words; the screen moves the focus itself (BLD-F098), so the picker does not take it on opening. Escape closes it
 * (the screen puts focus back on the "+").
 */
export function ConvoPicker({
  id,
  help,
  link,
  onLinkDraft,
  onFiles,
  onLink,
  onClose,
}: {
  id: string;
  help: string | null;
  /** The link field as the screen keeps it (BLD-F102). */
  link: LinkDraft;
  onLinkDraft(next: LinkDraft): void;
  onFiles(files: File[]): void;
  /** A link as typed, to go into the words. */
  onLink(link: string): void;
  onClose(): void;
}) {
  return (
    <FilePicker
      id={id}
      className="cv-pick"
      help={help}
      autoFocus={false}
      link={link}
      onLinkDraft={onLinkDraft}
      onFiles={onFiles}
      onLinks={(_, typed) => onLink(typed)}
      onClose={onClose}
    />
  );
}
