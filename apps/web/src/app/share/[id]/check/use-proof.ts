"use client";

/**
 * "Anything that shows it?" as state (C-FILE.row, C-FILE.uploader, A-API.files): the rows, and what adding, trying
 * again, hiding and removing a file or link does to them. Check it (S-05) uses it for a draft and the edit page
 * (S-06B) for a shared idea, so a file behaves the same on both. A file never blocks the others (C-FILE.uploader/4);
 * rows that are still moving on the server (scan, then the personal-details check) are asked again until they
 * settle. No words are logged here (non-negotiable 3).
 */
import { useCallback, useEffect, useState } from "react";

import type { FileItem } from "@/lib/contracts";

import { api, type Call, type ProofTarget } from "./client";
import { settling, type ProofItem } from "./model";

/** Every call the page makes, so its save status can follow it (C-TASKBAR.save). */
export type Track = <T>(p: Promise<Call<T>>) => Promise<Call<T>>;

export function useProof(to: string | ProofTarget, track: Track, limitMb: number) {
  const [proof, setProof] = useState<ProofItem[]>([]);

  const replace = useCallback(
    (key: string, next: Partial<ProofItem>) =>
      setProof((list) => list.map((p) => (p.key === key ? { ...p, ...next } : p))),
    [],
  );

  /** The rows as the server last sent them (on load, or after a save). */
  const load = useCallback(
    (files: FileItem[]) => setProof(files.map((f) => ({ key: f.id, item: f, name: f.name }))),
    [],
  );

  const upload = async (key: string, file: File) => {
    replace(key, { localState: "uploading", refusal: undefined });
    const r = await track(api.upload(to, file));
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

  const addLinks = async (links: string[]): Promise<"ok" | "not_a_link" | "failed"> => {
    for (const url of links) {
      const r = await track(api.link(to, url));
      if (!r.ok) return r.error?.code === "not_a_link" ? "not_a_link" : "failed";
      const item = r.body;
      setProof((list) => [...list, { key: item.id, item, name: item.name || url }]);
    }
    return "ok";
  };

  const retryFile = async (key: string) => {
    const p = proof.find((x) => x.key === key);
    if (!p) return;
    if (p.item?.id && !p.localState) {
      replace(key, { item: { ...p.item, state: "uploading" } });
      const r = await track(api.retryFile(p.item.id));
      replace(key, r.ok && r.body ? { item: r.body } : { item: { ...p.item, state: "upload_failed" } });
    } else if (p.local) await upload(key, p.local);
  };

  const hideFile = async (key: string) => {
    const p = proof.find((x) => x.key === key);
    if (!p?.item?.id) return;
    const r = await track(api.hideFile(p.item.id));
    if (r.ok && r.body) replace(key, { item: r.body });
  };

  const removeFile = async (key: string) => {
    const p = proof.find((x) => x.key === key);
    setProof((list) => list.filter((x) => x.key !== key));
    if (p?.item?.id) {
      const r = await track(api.removeFile(p.item.id));
      if (!r.ok && r.status !== 404)
        setProof((list) => (list.some((x) => x.key === key) ? list : [...list, p]));
    }
  };

  // Files settle on the server (scan, then the personal-details check): ask again until they do (C-FILE.row).
  useEffect(() => {
    const moving = proof.filter(settling);
    if (!moving.length) return;
    const t = setTimeout(async () => {
      for (const p of moving) {
        if (!p.item?.id) continue;
        const r = await api.file(p.item.id);
        if (r.ok && r.body) replace(p.key, { item: r.body });
      }
    }, 2000);
    return () => clearTimeout(t);
  }, [proof, replace]);

  return { proof, load, addFiles, addLinks, retryFile, hideFile, removeFile };
}
