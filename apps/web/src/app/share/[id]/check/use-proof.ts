"use client";

/**
 * "Anything that shows it?" as state (C-FILE.row, C-FILE.uploader, A-API.files): the rows, and what adding, trying
 * again, hiding and removing a file or link does to them. Check it (S-05) uses it for a draft and the edit page
 * (S-06B) for a shared idea, and the prompt box (S-03, S-04, S-04B; `share/box-files.tsx`) for the draft it may first
 * have to make (`resolve`, BLD-C214), so a file behaves the same everywhere. A file never blocks the others
 * (C-FILE.uploader/4); rows that are still moving on the server (scan, then the personal-details check) are asked
 * again until they settle. No words are logged here (non-negotiable 3).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import type { FileItem } from "@/lib/contracts";

import { api, type Call, type ProofTarget } from "./client";
import { CHECK_COPY } from "./copy";
import { POLL, pollDelay, settling, waitingForCheck, type ProofItem } from "./model";
import type { LinkResult } from "./proof";

/** Every call the page makes, so its save status can follow it (C-TASKBAR.save). */
export type Track = <T>(p: Promise<Call<T>>) => Promise<Call<T>>;

/** Where a row goes when the page has no draft yet: the prompt box on Home and Share a problem makes the draft on
 * the first file (C-PROMPT.attach, BLD-C214). Resolves to null when it could not be made. */
export type ResolveTarget = () => Promise<string | ProofTarget | null>;

const NOT_SENT: Call<FileItem> = { ok: false, status: 0, error: null };

export function useProof(
  to: string | ProofTarget | null,
  track: Track,
  limitMb: number,
  resolve?: ResolveTarget,
) {
  const [proof, setProof] = useState<ProofItem[]>([]);
  // The target as the latest render has it, and how to make one, for uploads that start before a re-render.
  const target = useRef({ to, resolve });
  useEffect(() => {
    target.current = { to, resolve };
  });
  /** The draft or idea for a new row: the one the page has, or the one `resolve` makes (once, by the caller). */
  const where = useCallback(async (): Promise<string | ProofTarget | null> => {
    const t = target.current;
    return t.to ?? (t.resolve ? await t.resolve() : null);
  }, []);

  const replace = useCallback(
    (key: string, next: Partial<ProofItem>) =>
      setProof((list) => list.map((p) => (p.key === key ? { ...p, ...next } : p))),
    [],
  );

  /** Rows removed while their upload was still on its way: the file is deleted when the POST answers. */
  const removedEarly = useRef(new Set<string>());
  /** Failed asks in a row for each moving file (C-FILE.row polling, BLD-C139). */
  const pollFails = useRef(new Map<string, number>());
  const [pollTick, setPollTick] = useState(0);
  /** Each upload still on its way, so a removal that must know the outcome can wait for it (S-06B's Cancel). */
  const pending = useRef(new Map<string, Promise<Call<FileItem>>>());
  /** Removals of files that were still uploading: each resolves to true once nothing of it is left on the server. */
  const early = useRef(new Map<string, Promise<boolean>>());
  const [earlyCount, setEarlyCount] = useState(0);
  /** The server's words (or the drawn line) for a file removed while uploading that could not be deleted when its
   * upload answered: it has no row left to show them under, so the page shows them by the files (S-06B). */
  const [leftover, setLeftover] = useState<string | null>(null);

  /** The rows as the server last sent them (on load, or after a save). */
  const load = useCallback(
    (files: FileItem[]) => setProof(files.map((f) => ({ key: f.id, item: f, name: f.name }))),
    [],
  );

  const upload = async (key: string, file: File) => {
    replace(key, { localState: "uploading", refusal: undefined, note: undefined });
    const to = target.current.to;
    const posted = track(
      to ? api.upload(to, file) : where().then((made) => (made ? api.upload(made, file) : NOT_SENT)), // no draft could be made: Try again
    );
    pending.current.set(key, posted);
    const r = await posted;
    pending.current.delete(key);
    if (removedEarly.current.has(key)) {
      // Removed during the upload: what reached the server goes too (`early`, which reports how it went).
      removedEarly.current.delete(key);
      if (!early.current.has(key) && r.ok && r.body?.id) void track(api.removeFile(r.body.id));
      return;
    }
    if (r.ok) {
      replace(key, {
        item: r.body,
        localState: undefined,
        refusal: undefined,
        note: undefined, // "still uploading" no longer holds (BLD-B283)
        name: r.body?.name || file.name,
      });
      return;
    }
    // A-API.files: `too_big` (with `limit_mb`), `type_not_allowed`, `locked`, `forbidden`, `not_found` are refusals
    // in the server's words; anything else (the network, the server) is "Didn't upload…" with Try again.
    const code = r.error?.code;
    const words = r.error?.message || undefined;
    if (r.status === 413 || code === "too_big") replace(key, { localState: "too_big", refusal: words });
    else if (code && ["type_not_allowed", "locked", "forbidden", "not_found"].includes(code)) {
      replace(key, { localState: "refused", refusal: words });
    } else replace(key, { localState: "upload_failed" });
  };

  const addFiles = (files: File[]) => {
    const fresh = files.map((file, i) => ({
      key: `local-${Date.now()}-${i}-${file.name}`,
      item: null,
      local: file,
      name: file.name,
      localState: file.size > limitMb * 1024 * 1024 ? ("too_big" as const) : ("uploading" as const),
    }));
    setProof((list) => [...list, ...fresh]);
    for (const f of fresh) if (f.localState === "uploading") void upload(f.key, f.local);
  };

  /** Links one by one (C-FILE.uploader/3): each added link is a row; the ones that failed are handed back to stay in
   * the box, and a link already on the page is never added twice, so trying again never duplicates one. */
  const addLinks = async (links: string[]): Promise<LinkResult> => {
    const have = new Set(proof.map((p) => p.item?.url ?? p.item?.name ?? p.name));
    const left: string[] = [];
    let problem: LinkResult["problem"] = null;
    const fresh = links.filter((url) => !have.has(url));
    if (!fresh.length) return { left, problem };
    const to = target.current.to ?? (await where());
    if (!to) return { left: fresh, problem: "failed" }; // no draft could be made: the links stay in the box
    for (const url of links) {
      if (have.has(url)) continue;
      const r = await track(api.link(to, url));
      if (!r.ok) {
        left.push(url);
        if (r.error?.code === "not_a_link") problem = "not_a_link";
        else problem ??= "failed";
        continue;
      }
      const item = r.body;
      have.add(url);
      setProof((list) =>
        list.some((x) => x.key === item.id)
          ? list
          : [...list, { key: item.id, item, name: item.name || url }],
      );
    }
    return { left, problem };
  };

  const retryFile = async (key: string) => {
    const p = proof.find((x) => x.key === key);
    if (!p) return;
    if (p.stalled) {
      // Asking for its state had stopped: ask again, from the start.
      pollFails.current.delete(key);
      replace(key, { stalled: false, note: undefined });
      return;
    }
    if (p.item?.id && !p.localState) {
      replace(key, { item: { ...p.item, state: "uploading" } });
      const r = await track(api.retryFile(p.item.id));
      replace(key, r.ok && r.body ? { item: r.body } : { item: { ...p.item, state: "upload_failed" } });
    } else if (p.local) await upload(key, p.local);
  };

  const hideFile = async (key: string) => {
    const p = proof.find((x) => x.key === key);
    if (!p?.item?.id) return;
    replace(key, { note: undefined });
    const r = await track(api.hideFile(p.item.id));
    // `files.blackout` off answers 503 `not_available`: the server's words under the row (C-FIELD-MSG).
    if (r.ok && r.body) replace(key, { item: r.body });
    else replace(key, { note: (!r.ok && r.error?.message) || CHECK_COPY.failed });
  };

  /** Deletes one file the server has: the row goes once the server agrees; if it does not, the row stays where it
   * is with the server's words (or the drawn line) under it. True when nothing of it is left on the server. */
  const deleteOne = async (key: string, fileId: string): Promise<boolean> => {
    replace(key, { note: undefined });
    const r = await track(api.removeFile(fileId));
    if (r.ok || r.status === 404) {
      pollFails.current.delete(key);
      setProof((list) => list.filter((x) => x.key !== key));
      return true;
    }
    replace(key, { note: r.error?.message || CHECK_COPY.failed });
    return false;
  };

  /**
   * Remove takes the row away once the server agrees; if it does not, the row stays where it is and says so. Resolves
   * to true when nothing of the row is left on the server. A row still uploading goes at once and its file is deleted
   * when the POST answers; with `wait` (S-06B's Cancel, which must know the outcome before it leaves) the POST is
   * waited for and its file deleted before this answers.
   */
  const removeFile = async (key: string, opts: { wait?: boolean } = {}): Promise<boolean> => {
    const p = proof.find((x) => x.key === key);
    if (!p) return true;
    if (p.item?.id) return deleteOne(key, p.item.id);
    if (p.localState === "uploading") {
      const posted = pending.current.get(key);
      if (posted && opts.wait) {
        const r = await posted;
        if (r.ok && r.body?.id) return deleteOne(key, r.body.id);
        setProof((list) => list.filter((x) => x.key !== key));
        return true;
      }
      removedEarly.current.add(key);
      if (posted) {
        // The row goes now; what the upload put on the server is deleted when it answers, and how that went is kept
        // (`settleEarly`), so nothing is left behind unsaid.
        const gone = posted
          .then(async (r) => {
            if (!(r.ok && r.body?.id)) return true;
            const d = await track(api.removeFile(r.body.id));
            if (d.ok || d.status === 404) return true;
            setLeftover((!d.ok && d.error?.message) || CHECK_COPY.failed);
            return false;
          })
          .finally(() => {
            early.current.delete(key);
            setEarlyCount((n) => n - 1);
          });
        early.current.set(key, gone);
        setEarlyCount((n) => n + 1);
      }
    }
    setProof((list) => list.filter((x) => x.key !== key));
    return true;
  };

  /** Waits for every file removed while it was uploading: true when none of them is left on the server. */
  const settleEarly = async (): Promise<boolean> =>
    (await Promise.all(Array.from(early.current.values()))).every(Boolean);

  /** Waits for every upload still on its way, so a page that moves on finds each file on the draft (BLD-C214). */
  const settleUploads = useCallback(async (): Promise<void> => {
    await Promise.all(Array.from(pending.current.values()));
  }, []);

  // Files settle on the server (scan, then the personal-details check): ask again until they do (C-FILE.row). A
  // failed ask (the network, a 4xx while a switch is off) waits longer and asks again; after five in a row the row
  // offers "Try again" rather than freezing (BLD-C139). While every moving file waits for the gatekeeper, every
  // 30 s (BLD-C236).
  useEffect(() => {
    const moving = proof.filter(settling);
    if (!moving.length) return;
    const worst = Math.max(0, ...moving.map((p) => pollFails.current.get(p.key) ?? 0));
    const t = setTimeout(
      async () => {
        let again = false;
        for (const p of moving) {
          if (!p.item?.id) continue;
          const r = await api.file(p.item.id);
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
      },
      pollDelay(worst, moving.every(waitingForCheck)),
    );
    return () => clearTimeout(t);
  }, [proof, pollTick, replace]);

  /** A refusal about one file (Submit's `file_blocked`): the server's words under its row. `id` is the file's id, or
   * the row's own key for a file still uploading in this browser, which has no id yet (BLD-B283). */
  const noteFile = useCallback(
    (id: string, note: string) =>
      setProof((list) => list.map((p) => (p.item?.id === id || p.key === id ? { ...p, note } : p))),
    [],
  );

  return {
    proof,
    load,
    addFiles,
    addLinks,
    retryFile,
    hideFile,
    removeFile,
    noteFile,
    /** A file removed while uploading is still being deleted. */
    removing: earlyCount > 0,
    settleEarly,
    settleUploads,
    leftover,
  };
}
