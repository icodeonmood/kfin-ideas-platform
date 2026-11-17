"use client";

/**
 * "Anything that shows it?" as state (C-FILE.row, C-FILE.uploader, A-API.files): the rows, and what adding, trying
 * again, hiding and removing a file or link does to them. Check it (S-05) uses it for a draft and the edit page
 * (S-06B) for a shared idea, so a file behaves the same on both. A file never blocks the others (C-FILE.uploader/4);
 * rows that are still moving on the server (scan, then the personal-details check) are asked again until they
 * settle. No words are logged here (non-negotiable 3).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import type { FileItem } from "@/lib/contracts";

import { api, type Call, type ProofTarget } from "./client";
import { CHECK_COPY } from "./copy";
import { POLL, pollDelay, settling, type ProofItem } from "./model";
import type { LinkResult } from "./proof";

/** Every call the page makes, so its save status can follow it (C-TASKBAR.save). */
export type Track = <T>(p: Promise<Call<T>>) => Promise<Call<T>>;

export function useProof(to: string | ProofTarget, track: Track, limitMb: number) {
  const [proof, setProof] = useState<ProofItem[]>([]);

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

  /** The rows as the server last sent them (on load, or after a save). */
  const load = useCallback(
    (files: FileItem[]) => setProof(files.map((f) => ({ key: f.id, item: f, name: f.name }))),
    [],
  );

  const upload = async (key: string, file: File) => {
    replace(key, { localState: "uploading", refusal: undefined, note: undefined });
    const posted = track(api.upload(to, file));
    pending.current.set(key, posted);
    const r = await posted;
    pending.current.delete(key);
    if (removedEarly.current.has(key)) {
      // Removed during the upload: what reached the server goes too, so nothing is left behind.
      removedEarly.current.delete(key);
      if (r.ok && r.body?.id) void track(api.removeFile(r.body.id));
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
    }
    setProof((list) => list.filter((x) => x.key !== key));
    return true;
  };

  // Files settle on the server (scan, then the personal-details check): ask again until they do (C-FILE.row). A
  // failed ask (the network, a 4xx while a switch is off) waits longer and asks again; after five in a row the row
  // offers "Try again" rather than freezing (BLD-C139).
  useEffect(() => {
    const moving = proof.filter(settling);
    if (!moving.length) return;
    const worst = Math.max(0, ...moving.map((p) => pollFails.current.get(p.key) ?? 0));
    const t = setTimeout(async () => {
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
    }, pollDelay(worst));
    return () => clearTimeout(t);
  }, [proof, pollTick, replace]);

  /** A refusal about one file (Submit's `file_blocked`): the server's words under its row. */
  const noteFile = useCallback(
    (fileId: string, note: string) =>
      setProof((list) => list.map((p) => (p.item?.id === fileId ? { ...p, note } : p))),
    [],
  );

  return { proof, load, addFiles, addLinks, retryFile, hideFile, removeFile, noteFile };
}
