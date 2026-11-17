"use client";

/**
 * S-05 "Check it, then send it" (steps 2 and 3 of 3; J-SHARE/7–11, the S-05 steps of J-SIMILAR and J-RECOVER).
 *
 * Desktop: the task bar, a rail of the seven parts, each with a one-line status that changes the moment its content
 * does (S-05.rules/2), and one part on stage at a time; parts slide forward and back (S-05.rules/1), and optional
 * parts skip with no extra clicks (/3). Phone: one scrolling page with the same parts in the same order, then the
 * declaration and Submit (S-05.phone). Every message sits under what it is about (S-05.rules/5); no snackbars.
 *
 * Data: the draft (A-API.drafts), its sorting, fix, helpers and the Send part's last look (lane C), similar ideas and
 * "Keep mine separate" (c/similar), files and links (A-API.files), the merge request (lane F). Submit sends the
 * declaration's version with an idempotency key and hands over to S-06 with the idea's reference (L-SUBMIT.send).
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from "react";

import { IconTick } from "@/components/shell/icons";
import { Taskbar, type SaveState } from "@/components/shell/taskbar";
import type { TeamUpSent } from "@/components/teamup/teamup-sheet";
import { Button, ButtonLink } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { Loading, SkeletonRows } from "@/components/ui/skeleton";
import type {
  ApiError,
  ConfigResponse,
  HiddenDetail,
  SendViewResponse,
  ShowReason,
  SortingResponse,
  UploadConfig,
} from "@/lib/contracts";

import { api, sendKey, sendQueue, type Call, type CheckDraft, type MergeState } from "./client";
import { CHECK_COPY, PARTS, type PartNo } from "./copy";
import { FixPartBody, FixSheet, typedAnything, type FixPart, type FixProblem } from "./fix";
import { HiddenTile } from "./hidden";
import {
  EMPTY_FIX,
  fixFormFrom,
  fixRequest,
  mergeView,
  oneLine,
  partFromStep,
  rowView,
  similarRail,
  sortingCount,
  stepOf,
  type FixForm,
  type SimilarLoad,
  type TileAction,
} from "./model";
import {
  BackToWords,
  HelpersBody,
  PartFrame,
  SendBar,
  SendRows,
  SortingBody,
  WordsBody,
  type SendState,
} from "./parts";
import { ProofBody } from "./proof";
import { SimilarGrid } from "./similar";
import { useProof } from "./use-proof";

import "./check.css";

const C = CHECK_COPY;
const DEFAULT_LIMIT_MB = 25;

// ---------------------------------------------------------------------------------------------------------------
// Small browser hooks
// ---------------------------------------------------------------------------------------------------------------

function subscribeOnline(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

const PHONE = "(max-width: 720px)";

function subscribePhone(cb: () => void) {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const m = window.matchMedia(PHONE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}

export function usePhone(): boolean {
  return useSyncExternalStore(
    subscribePhone,
    () => typeof window.matchMedia === "function" && window.matchMedia(PHONE).matches,
    () => false,
  );
}

// ---------------------------------------------------------------------------------------------------------------
// The screen
// ---------------------------------------------------------------------------------------------------------------

export function CheckIt({
  draftId,
  config: initialConfig,
  blackout = false,
}: {
  draftId: string;
  config: ConfigResponse | null;
  /** `files.blackout` (DEC-107, BLD-C064): "Hide it for me" on a file is offered only while it is on. */
  blackout?: boolean;
}) {
  const router = useRouter();
  const online = useOnline();
  const phone = usePhone();

  const [draft, setDraft] = useState<CheckDraft | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [config, setConfig] = useState<ConfigResponse | null>(initialConfig);
  const [uploads, setUploads] = useState<UploadConfig | null>(null);
  const [part, setPart] = useState<PartNo>(1);
  const [dir, setDir] = useState<1 | -1>(1);
  const [done, setDone] = useState<ReadonlySet<PartNo>>(new Set());

  const [sorting, setSorting] = useState<SortingResponse | null>(null);
  const [sortError, setSortError] = useState<string | null>(null);
  const [triedUnconfirmed, setTriedUnconfirmed] = useState(false);

  const [similar, setSimilar] = useState<SimilarLoad>({ state: "loading" });
  const [merge, setMerge] = useState<MergeState | null>(null);
  const [kept, setKept] = useState(false);
  const [mergeError, setMergeError] = useState<{ where: "bar" | "grid"; text: string } | null>(null);

  const [fixPart, setFixPart] = useState<FixPart>({ kind: "none" });
  const [fixForm, setFixForm] = useState<FixForm>(EMPTY_FIX);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [fixError, setFixError] = useState<string | null>(null);
  const [removingFix, setRemovingFix] = useState(false);

  const [helpers, setHelpers] = useState<{ picks: string[]; text: string }>({ picks: [], text: "" });
  const [helpersError, setHelpersError] = useState<string | null>(null);

  const [sendView, setSendView] = useState<SendViewResponse | null>(null);
  const [sendLoad, setSendLoad] = useState<"idle" | "failed">("idle");
  const [sendState, setSendState] = useState<SendState>({ kind: "idle" });
  /** Bumped when a send kept on this device is found on load, so it is sent once the page is ready. */
  const [replay, setReplay] = useState(0);
  /** Submit's `not_ready` for the title or what happens, shown under that line on part 1. */
  const [wordErrors, setWordErrors] = useState<Partial<Record<"title" | "summary", string>>>({});

  const [save, setSave] = useState<SaveState>("saved");
  const [savedAt, setSavedAt] = useState<Date | string | null>(null);

  const heading = useRef<HTMLHeadingElement>(null);
  const railStatusId = useId();
  const moved = useRef(false);
  const idemKey = useRef<string | null>(null);
  const queued = useRef(false);
  const writes = useRef(0);
  const helperTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** The latest picks and words, so a save that waits for typing to pause never sends picks from before a click. */
  const helpersNow = useRef<{ picks: string[]; text: string }>({ picks: [], text: "" });

  /** A write the task bar's save status follows: "Saving…", then "Saved at 1:38 pm" (C-TASKBAR.save). */
  const track = useCallback(async <T,>(p: Promise<Call<T>>): Promise<Call<T>> => {
    writes.current += 1;
    setSave("saving");
    const r = await p;
    writes.current -= 1;
    if (r.ok) {
      setSavedAt(new Date());
      if (writes.current === 0) setSave("saved");
    } else if (writes.current === 0) setSave(navigator.onLine ? "saved" : "offline");
    return r;
  }, []);

  const limits = uploads ?? config?.uploads ?? null;
  const limitMb = limits?.limit_mb ?? DEFAULT_LIMIT_MB;
  // Part 4's rows and what adding, retrying, hiding and removing does (use-proof.ts, shared with the edit page).
  const {
    proof,
    load: loadProof,
    addFiles,
    addLinks,
    retryFile,
    hideFile,
    removeFile,
    noteFile,
  } = useProof(draftId, track, limitMb);

  // --- Loading ----------------------------------------------------------------------------------------------------

  const loadSimilar = useCallback(async () => {
    const [s, m] = await Promise.all([api.similar(draftId), api.merge(draftId)]);
    setSimilar(s.ok && Array.isArray(s.body) ? { state: "ok", matches: s.body } : { state: "failed" });
    if (m.ok && m.body && typeof m.body === "object") setMerge(m.body);
  }, [draftId]);

  const fetchAll = useCallback(
    () =>
      Promise.all([
        api.draft(draftId),
        api.sorting(draftId),
        initialConfig ? Promise.resolve(null) : api.config(),
        api.uploads(),
      ]),
    [draftId, initialConfig],
  );

  const apply = useCallback(
    ([d, s, cfg, up]: Awaited<ReturnType<typeof fetchAll>>) => {
      if (!d.ok || !d.body) {
        setLoadFailed(true);
        return;
      }
      setLoadFailed(false);
      const body = d.body;
      setDraft(body);
      setSavedAt(body.saved_at ?? null);
      setPart(partFromStep(body.step));
      if (s.ok) setSorting(s.body);
      if (cfg && cfg.ok) setConfig(cfg.body);
      if (up.ok && up.body && typeof up.body.limit_mb === "number") setUploads(up.body);
      setKept(Boolean(body.kept_separate));
      loadProof(body.files ?? []);
      const asked = body.merge_request;
      if (asked && asked.state !== "none") setMerge((m) => m ?? { ...asked, after: null });
      const fix = body.fix;
      if (fix && fix.how && fix.included) {
        setFixPart({ kind: "added", line: C.fix.included(fix.ready_count), fixLine: oneLine(fix.how) });
      } else if (fix) setFixPart({ kind: "started" });
      setFixForm(fixFormFrom(fix));
      const saved = { picks: body.helpers?.picks ?? [], text: body.helpers?.text ?? "" };
      helpersNow.current = saved;
      setHelpers(saved);
      const waiting = sendQueue.load(draftId);
      if (waiting) {
        idemKey.current = waiting;
        queued.current = true;
        setSendState({ kind: "queued" });
        setReplay((n) => n + 1);
      }
      void loadSimilar();
    },
    [loadSimilar, loadProof, draftId],
  );

  useEffect(() => {
    let live = true;
    void fetchAll().then((r) => {
      if (live) apply(r);
    });
    return () => {
      live = false;
    };
  }, [fetchAll, apply]);

  const applySend = useCallback((r: Call<SendViewResponse>) => {
    if (r.ok) {
      setSendView(r.body);
      setSendLoad("idle");
    } else setSendLoad("failed");
  }, []);

  const loadSend = useCallback(async () => applySend(await api.send(draftId)), [draftId, applySend]);

  // On a phone the last look is on the same page as everything else.
  useEffect(() => {
    if (!phone || !draft || sendView || sendLoad !== "idle") return;
    let live = true;
    void api.send(draftId).then((r) => {
      if (live) applySend(r);
    });
    return () => {
      live = false;
    };
  }, [phone, draft, sendView, sendLoad, draftId, applySend]);

  // --- Moving between parts ---------------------------------------------------------------------------------------

  const go = useCallback(
    (n: PartNo, opts: { forwardFrom?: PartNo } = {}) => {
      if (phone) {
        // One page: "Go to the sorting", a Send row's "Change" and "Change the attached files" take the person to
        // that part's heading, scrolled to and focused (L-SORT.rules/4, WCAG 2.4.3).
        const h = document.querySelector<HTMLElement>(`[data-part="${n}"] .ck-h`);
        h?.scrollIntoView?.({ block: "start" });
        h?.focus({ preventScroll: true });
        return;
      }
      setDir(n >= part ? 1 : -1);
      if (opts.forwardFrom) {
        const from = opts.forwardFrom;
        setDone((s) => new Set([...s, from]));
      }
      moved.current = true;
      setPart(n);
      if (n === 7) {
        // A message from an earlier try is about a state that may have changed since; the last look is read again.
        setSendState((st) => (st.kind === "sending" || st.kind === "queued" ? st : { kind: "idle" }));
        void loadSend();
      }
      void api.step(draftId, stepOf(n));
    },
    [draftId, part, loadSend, phone],
  );

  useEffect(() => {
    if (!moved.current || phone) return;
    heading.current?.focus();
  }, [part, phone]);

  // --- Part 1: your words, hidden details --------------------------------------------------------------------------

  const saveWord = async (key: "title" | "summary" | "often", value: string) => {
    const r = await track(api.part(draftId, key, value));
    if (!r.ok) return false;
    if (key !== "often") setWordErrors((e) => ({ ...e, [key]: undefined }));
    const next = (r.body as { draft?: CheckDraft } | null)?.draft;
    setDraft(
      (d) =>
        next ?? (d ? { ...d, parts: { ...d.parts, [key]: { ...d.parts[key], value, state: "pinned" } } } : d),
    );
    return true;
  };

  const updateHidden = (h: HiddenDetail) =>
    setDraft((d) => (d ? { ...d, hidden: d.hidden.map((x) => (x.id === h.id ? h : x)) } : d));

  const showHidden = async (id: string, reason: ShowReason) => {
    const r = await track(api.showHidden(draftId, id, reason));
    if (r.ok && r.body) updateHidden(r.body);
    return r.ok;
  };

  const hideAgain = async (id: string) => {
    const r = await track(api.hideAgain(draftId, id));
    if (r.ok && r.body) updateHidden(r.body);
    return r.ok;
  };

  // --- Part 2: sorting ---------------------------------------------------------------------------------------------

  const changeSorting = async (patch: Parameters<typeof api.patchSorting>[1]) => {
    setSortError(null);
    const r = await track(api.patchSorting(draftId, patch));
    if (r.ok) setSorting(r.body);
    else setSortError(r.error?.message || C.failed);
  };

  const confirmSorting = async () => {
    setSortError(null);
    const r = await track(api.patchSorting(draftId, { confirm: true }));
    if (!r.ok) {
      setSortError(r.error?.message || C.failed);
      return;
    }
    setSorting(r.body);
    if (r.body.confirmed) {
      setTriedUnconfirmed(false);
      if (!phone) go(3, { forwardFrom: 2 });
    }
  };

  // --- Part 3: similar ideas ---------------------------------------------------------------------------------------

  const matches = similar.state === "ok" ? similar.matches : [];
  const mv = mergeView(merge, matches);

  /** A failed Withdraw says so where it was pressed: on the bar under the task bar, or under the grid. */
  const withdraw = async (
    action: Extract<TileAction, { kind: "waiting" }>,
    where: "bar" | "grid" = "grid",
  ) => {
    setMergeError(null);
    const r =
      "merge" in action.withdraw
        ? await track(api.withdrawMerge(draftId))
        : await track(api.withdrawTeamUp(action.withdraw.requestId));
    if (!r.ok) setMergeError({ where, text: r.error?.message || C.failed });
    await loadSimilar();
  };

  const mergeAction = async () => {
    const a = mv?.action;
    if (!a) return;
    if (a.op === "withdraw") await withdraw({ kind: "waiting", label: "", withdraw: { merge: true } }, "bar");
    else if (a.op === "submit") go(7);
  };

  // "Next" only moves on: it records nothing. Only an explicit "Keep mine separate" in lane F's sheet does, so the
  // review desk never reads "kept it separate" for someone who only carried on (BLD-C131, as amended).
  const similarNext = () => go(4, { forwardFrom: 3 });

  /** The sheet's send. "Keep mine separate" is a team-up request sent with the draft (BLD-F020, BLD-F071): the
   * draft is kept separate and the grid folds (C-SIMGRID.grid/4, V-ACC.share/7); a merge request reloads the bar.
   * The grid folds only once the server has recorded it; if it has not, the grid stays and the drawn line under it
   * says so, so the person can choose again (BLD-C131). */
  const teamUpSent = async (sent: TeamUpSent) => {
    if (sent.kind === "teamup") {
      setMergeError(null);
      const r = await track(api.keepSeparate(draftId, true));
      if (r.ok) setKept(true);
      else setMergeError({ where: "grid", text: C.failed });
    }
    void loadSimilar();
  };

  const showAgain = async () => {
    const r = await track(api.keepSeparate(draftId, false));
    if (r.ok) setKept(false);
  };

  // --- Part 5: the fix ---------------------------------------------------------------------------------------------

  const addFix = async (form: FixForm) => {
    const r = await track(api.putFix(draftId, fixRequest(form, true)));
    if (!r.ok) {
      const code = r.error?.code;
      const message = r.error?.message;
      if (code === "fix_how_needed" || r.error?.field === "how") {
        return { field: "how" as const, message: message || C.sheet.howNeeded };
      }
      if (code === "worth_unclear")
        return { field: "worth" as const, message: message || C.sheet.worthUnclear };
      return { field: null, message: message || C.failed };
    }
    const p = r.body.part;
    setFixPart(
      p.rail === "Added"
        ? { kind: "added", line: p.line, fixLine: p.fix_line, sizeLine: p.size_line }
        : { kind: "started" },
    );
    setFixForm(form);
    setSheetOpen(false);
    return null;
  };

  /** The cross, "Close, and keep what you wrote": saved first, closed after, so nothing is lost on a failed save.
   * A figure the server cannot read (`worth_unclear`) keeps the sheet open with its line under the figure. */
  const keepFix = async (form: FixForm): Promise<FixProblem | null> => {
    // An added fix stays as it was; a sheet with nothing typed just closes.
    if (fixPart.kind === "added" || !typedAnything(form)) {
      setSheetOpen(false);
      return null;
    }
    const r = await track(api.putFix(draftId, fixRequest(form, false)));
    if (!r.ok) {
      if (r.error?.code === "worth_unclear") {
        return { field: "worth", message: r.error.message || C.sheet.worthUnclear };
      }
      return { field: null, message: r.error?.message || C.failed };
    }
    setFixForm(form);
    setFixPart({ kind: "started" });
    setFixError(null);
    setSheetOpen(false);
    return null;
  };

  const removeFix = async () => {
    setRemovingFix(true);
    const r = await track(api.removeFix(draftId));
    setRemovingFix(false);
    if (r.ok) {
      setFixPart({ kind: "none" });
      setFixForm(EMPTY_FIX);
      setFixError(null);
    } else setFixError(C.failed);
  };

  // --- Part 6: who would help --------------------------------------------------------------------------------------

  const putHelpers = useCallback(
    async (next: { picks: string[]; text: string }) => {
      const r = await track(
        api.putHelpers(draftId, { picks: next.picks, text: next.text.trim() || undefined }),
      );
      setHelpersError(r.ok ? null : C.failed);
    },
    [draftId, track],
  );

  const pickHelpers = (picks: string[]) => {
    const next = { ...helpersNow.current, picks };
    helpersNow.current = next;
    setHelpers(next);
    if (helperTimer.current) clearTimeout(helperTimer.current);
    void putHelpers(next);
  };

  const typeHelpers = (text: string) => {
    const next = { ...helpersNow.current, text };
    helpersNow.current = next;
    setHelpers(next);
    if (helperTimer.current) clearTimeout(helperTimer.current);
    helperTimer.current = setTimeout(() => {
      helperTimer.current = null;
      void putHelpers(helpersNow.current);
    }, 700);
  };

  // --- Part 7: send ------------------------------------------------------------------------------------------------

  const sortingUnconfirmed =
    sorting !== null
      ? !sorting.confirmed
      : Boolean(sendView?.go_to || sendView?.problems.some((p) => p.code === "sorting_unconfirmed"));
  const canSubmit = !(mv && !mv.canSubmit);

  /** Offline at Submit: kept on this device and sent when the connection is back (V-FIELDS.checkit/14). */
  const queue = () => {
    idemKey.current ??= sendKey(draftId);
    sendQueue.save(draftId, idemKey.current);
    queued.current = true;
    setSendState({ kind: "queued" });
  };

  const submit = async () => {
    if (!navigator.onLine) {
      queue();
      return;
    }
    if (sortingUnconfirmed) {
      sendQueue.clear(draftId);
      setSendState({ kind: "unconfirmed" });
      return;
    }
    // Words typed for "Who would help" that are still waiting for a pause go first (S-05 part 6).
    if (helperTimer.current) {
      clearTimeout(helperTimer.current);
      helperTimer.current = null;
      await putHelpers(helpersNow.current);
    }
    let view = sendView;
    if (!view) {
      const v = await api.send(draftId);
      if (!v.ok) {
        if (v.status === 0 && !navigator.onLine) queue();
        else setSendState({ kind: "failed" });
        return;
      }
      view = v.body;
      setSendView(view);
    }
    setSendState({ kind: "sending" });
    idemKey.current ??= sendKey(draftId);
    const r = await api.submit(draftId, view.declaration.version, idemKey.current);
    if (r.ok) {
      sendQueue.clear(draftId);
      const to = r.body.next?.to || `/ideas/${encodeURIComponent(r.body.ref || r.body.idea_id)}`;
      router.replace(to);
      return;
    }
    if (r.status === 0) {
      if (!navigator.onLine) queue();
      else setSendState({ kind: "failed" });
      return;
    }
    // The server answered: nothing is left to send from this device.
    sendQueue.clear(draftId);
    refused(r.error);
  };

  /** A refusal goes where it is about (S-05.rules/5, A-API POST /drafts/:id/submit): the file's row, the words, the
   * sorting, or its own line under Submit; only a failure with no answer is "Couldn't send…" with Try again. */
  const refused = (error: ApiError["error"] | null) => {
    const code = error?.code;
    const message = error?.message || "";
    const field = error?.field;
    if (code === "sorting_unconfirmed") {
      // Not confirmed, or confirmed with a field left empty: the server's own line for which (L-SORT.rules/2).
      setSendState({ kind: "unconfirmed", message: message || undefined });
      return;
    }
    if (code === "file_blocked" && field && proof.some((p) => p.item?.id === field)) {
      noteFile(field, message || C.failed);
      setSendState({ kind: "idle" });
      go(4);
      return;
    }
    if (code === "not_ready" && (field === "title" || field === "summary")) {
      setWordErrors((e) => ({ ...e, [field]: message || C.failed }));
      setSendState({ kind: "idle" });
      go(1);
      return;
    }
    if (code === "not_a_draft") {
      // Already sent: its own line, and Submit stays unavailable rather than looping on Try again.
      setSendState({ kind: "refused", message: message || C.failed, final: true });
      return;
    }
    if (code === "not_ready") {
      // Any other part not ready (how often, for one): the server's words under Submit, never "Try again", which
      // would only meet the same refusal (S-05.rules/5).
      setSendState({ kind: "refused", message: message || C.failed });
      return;
    }
    if (
      message &&
      code &&
      ["merge_waiting", "file_blocked", "declaration_changed", "merged"].includes(code)
    ) {
      setSendState({ kind: "refused", message });
      void loadSend();
      return;
    }
    setSendState({ kind: "failed" });
  };

  // Offline at Submit, or a send kept on this device from an earlier visit: it goes when the connection is back,
  // with the page as it is then.
  const latestSubmit = useRef(submit);
  useEffect(() => {
    latestSubmit.current = submit;
  });
  useEffect(() => {
    if (online && queued.current) {
      queued.current = false;
      void latestSubmit.current();
    }
  }, [online, replay]);

  const goToSorting = () => {
    setTriedUnconfirmed(true);
    setSendState({ kind: "idle" });
    go(2);
  };

  // --- What each part shows ----------------------------------------------------------------------------------------

  if (loadFailed) {
    return (
      <div className="ck ck-loading">
        <FieldMsg>{C.failed}</FieldMsg>
        <Button
          variant="line"
          onClick={() => {
            setLoadFailed(false);
            void fetchAll().then(apply);
          }}
        >
          {C.retry}
        </Button>
      </div>
    );
  }
  if (!draft) {
    return (
      <div className="ck ck-loading">
        <Loading what={C.rail}>
          <SkeletonRows what={C.rail} rows={4} />
        </Loading>
      </div>
    );
  }

  const title = String(draft.parts?.title?.value ?? "");
  const summary = String(draft.parts?.summary?.value ?? "");
  const often = String(draft.parts?.often?.value ?? "");
  const attached = (draft.files ?? []).filter((f) => (f as { message_id?: string }).message_id);
  const controls = config?.sorting.controls;
  const helpersOptions = controls?.helpers ?? config?.sorting.helpers ?? [];
  const helpersAdded = helpers.picks.length > 0 || helpers.text.trim() !== "";
  const proofTrouble = proof.some((p) => {
    const s = rowView(p, limitMb).status;
    return s === "failed" || s === "found" || s === "too-big";
  });

  const rail: Record<PartNo, string> = {
    1: attached.length ? C.words.railFiles(attached.length) : C.words.rail,
    2: sorting?.rail ?? "",
    3: similarRail(similar, mv),
    4: proof.length ? C.proof.count(proof.length) : C.optional,
    5: fixPart.kind === "added" ? C.added : C.optional,
    6: helpersAdded ? C.added : C.optional,
    7: C.send.rail,
  };
  const attention: Record<PartNo, boolean> = {
    1: false,
    2: triedUnconfirmed && sortingUnconfirmed,
    3: mv?.state === "waiting",
    4: proofTrouble,
    5: false,
    6: false,
    7: false,
  };
  const isDone = (n: PartNo) =>
    !attention[n] &&
    (n === 2 ? Boolean(sorting?.confirmed) : done.has(n) || (n === 5 && fixPart.kind === "added"));

  const back = (n: PartNo) =>
    n === 1 ? (
      <BackToWords href={`/share/${encodeURIComponent(draftId)}`} />
    ) : (
      <Button variant="text" onClick={() => go((n - 1) as PartNo)}>
        {C.back}
      </Button>
    );
  const forward = (n: PartNo, filled: boolean) => (
    <Button variant={filled ? "primary" : "line"} onClick={() => go((n + 1) as PartNo, { forwardFrom: n })}>
      {filled ? C.next : C.skip}
    </Button>
  );

  const hiddenTile = (
    <HiddenTile
      id={phone ? "pr-hidden" : undefined}
      details={draft.hidden ?? []}
      onShow={showHidden}
      onHide={hideAgain}
    />
  );

  const content: Record<
    PartNo,
    { heading: string; line?: string; body: React.ReactNode; foot?: React.ReactNode }
  > = {
    1: {
      heading: phone ? C.phone.words : C.words.heading,
      line: phone ? undefined : C.words.line,
      body: (
        <WordsBody
          values={{ title, summary, often }}
          attached={attached}
          onSave={saveWord}
          errors={wordErrors}
          onAttached={() => go(4)}
          hidden={hiddenTile}
        />
      ),
      foot: (
        <>
          {back(1)}
          <Button onClick={() => go(2, { forwardFrom: 1 })}>{C.words.forward}</Button>
        </>
      ),
    },
    2: {
      heading: phone ? C.phone.sorting : C.sorting.heading,
      line: phone ? undefined : C.sorting.line,
      body:
        sorting && controls ? (
          <SortingBody
            sorting={sorting}
            controls={controls}
            onChange={(patch) => void changeSorting(patch as Parameters<typeof api.patchSorting>[1])}
            unconfirmedTried={triedUnconfirmed}
            error={sortError}
          />
        ) : (
          <>
            <SkeletonRows what={C.sorting.heading} rows={4} />
            {sortError ? <FieldMsg>{sortError}</FieldMsg> : null}
          </>
        ),
      foot: (
        <>
          {phone ? null : back(2)}
          <Button onClick={() => void confirmSorting()} disabled={!sorting}>
            {phone ? C.phone.confirm : C.sorting.forward}
          </Button>
        </>
      ),
    },
    3: {
      heading: phone ? C.phone.similar : C.similar.heading,
      line:
        similar.state === "failed"
          ? C.similar.couldnt
          : similar.state === "ok" && !matches.length
            ? C.similar.none
            : similar.state === "ok"
              ? phone
                ? C.phone.similarLine(matches.length)
                : C.similar.line(matches.length)
              : undefined,
      body:
        similar.state === "loading" ? (
          <SkeletonRows what={C.similar.heading} rows={3} />
        ) : (
          <>
            <SimilarGrid
              draftId={draftId}
              draftTitle={title}
              draftSummary={summary}
              load={similar}
              merge={mv}
              keptSeparate={kept}
              onShowAgain={() => void showAgain()}
              onSent={(sent) => void teamUpSent(sent)}
              onWithdrawn={() => void loadSimilar()}
              onWithdraw={(a) => withdraw(a, "grid")}
            />
            {mergeError?.where === "grid" ? <FieldMsg>{mergeError.text}</FieldMsg> : null}
          </>
        ),
      foot: (
        <>
          {back(3)}
          <Button onClick={similarNext}>{C.next}</Button>
        </>
      ),
    },
    4: {
      heading: C.proof.heading,
      line: phone ? C.phone.proofLine : C.proof.line,
      body: (
        <ProofBody
          items={proof}
          limitMb={limitMb}
          help={limits?.help_text || C.proof.dropHelp}
          accept={limits?.types?.length ? limits.types.join(",") : undefined}
          onFiles={addFiles}
          onLinks={addLinks}
          onRetry={(k) => void retryFile(k)}
          onHide={(k) => void hideFile(k)}
          onRemove={(k) => void removeFile(k)}
          showHelps={!phone}
          canHide={blackout}
        />
      ),
      foot: (
        <>
          {back(4)}
          {forward(4, proof.length > 0)}
        </>
      ),
    },
    5: {
      heading: phone ? C.phone.fix : C.fix.heading,
      line: phone ? C.phone.fixLine : C.fix.line,
      body: (
        <FixPartBody
          part={fixPart}
          onOpen={() => {
            setFixError(null);
            setSheetOpen(true);
          }}
          onRemove={() => void removeFix()}
          removing={removingFix}
          error={fixError}
        />
      ),
      foot: (
        <>
          {back(5)}
          {forward(5, fixPart.kind === "added")}
        </>
      ),
    },
    6: {
      heading: C.helpers.heading,
      line: C.helpers.line,
      body: (
        <HelpersBody
          options={helpersOptions}
          picks={helpers.picks}
          text={helpers.text}
          onPicks={pickHelpers}
          onText={typeHelpers}
          error={helpersError}
        />
      ),
      foot: (
        <>
          {back(6)}
          {forward(6, helpersAdded)}
        </>
      ),
    },
    7: {
      heading: C.send.heading,
      line: C.send.line,
      body: (
        <>
          {sendView ? (
            <SendRows view={sendView} onChange={(step) => go(partFromStep(step))} />
          ) : sendLoad === "failed" ? (
            <div className="ck-sendfail">
              <FieldMsg>{C.failed}</FieldMsg>
              <Button
                variant="line"
                size="sm"
                onClick={() => {
                  setSendLoad("idle");
                  void loadSend();
                }}
              >
                {C.retry}
              </Button>
            </div>
          ) : (
            <SkeletonRows what={C.send.heading} rows={6} />
          )}
          <SendBar
            declaration={sendView?.declaration.text ?? config?.declaration?.submit ?? ""}
            button={sendView?.button ?? C.send.submit}
            state={sendState}
            offline={!online}
            blockedLine={phone && mv && !mv.canSubmit ? mv.line : null}
            canSubmit={canSubmit}
            onSubmit={() => void submit()}
            onGoToSorting={goToSorting}
            back={phone ? null : back(7)}
          />
        </>
      ),
    },
  };

  // The live region is on the page before its words, so a merge outcome that arrives later is announced (WCAG
  // 4.1.3); a failed Withdraw pressed here says so here (C-FIELD-MSG).
  const bar = (
    <div className="ck-mlive" role="status">
      {mv ? (
        <div className={`ck-mbar ck-mbar-${mv.state}`}>
          <p>{mv.line}</p>
          {mv.action?.to ? (
            <ButtonLink variant="text-blue" href={mv.action.to}>
              {mv.action.label}
            </ButtonLink>
          ) : mv.action ? (
            <Button variant="text-blue" onClick={() => void mergeAction()}>
              {mv.action.label}
            </Button>
          ) : null}
          {mergeError?.where === "bar" ? <FieldMsg>{mergeError.text}</FieldMsg> : null}
        </div>
      ) : null}
    </div>
  );

  const taskbar = (
    <Taskbar
      step={part === 7 ? "send" : "check"}
      stepHrefs={{ tell: `/share/${encodeURIComponent(draftId)}` }}
      save={online ? save : "offline"}
      savedAt={savedAt}
      closeHref="/home"
    />
  );

  const sheet = (
    <FixSheet
      open={sheetOpen}
      initial={fixForm}
      onCancel={() => setSheetOpen(false)}
      onKeep={keepFix}
      onAdd={addFix}
    />
  );

  if (phone) {
    // PhoneReview.md: "1 detail hidden", "3 sortings", "2 similar ideas", each a link to its part. A count of none
    // is left out (NOT DRAWN), so no link points at a part with nothing to show (BLD-C138).
    const hiddenNow = (draft.hidden ?? []).filter((d) => d.state !== "shown").length;
    const counts = [
      { n: hiddenNow, words: C.phone.hiddenCount(hiddenNow), href: "#pr-hidden" },
      { n: sortingCount(sorting), words: C.phone.sortingsCount(sortingCount(sorting)), href: "#pr-sort-h" },
      { n: matches.length, words: C.phone.similarCount(matches.length), href: "#pr-sim-h" },
    ].filter((x) => x.n > 0);
    return (
      <div className="ck ck-phone">
        {taskbar}
        {bar}
        <div className="ck-ph">
          <h1 className="h1">{C.phone.heading}</h1>
          <p className="ck-line">{C.phone.line}</p>
          {counts.length ? (
            <div className="ck-stats">
              {counts.map((x) => (
                <a key={x.href} className="ck-stat" href={x.href}>
                  <b className="num">{x.n}</b> {x.words}
                </a>
              ))}
            </div>
          ) : null}
          <BackToWords href={`/share/${encodeURIComponent(draftId)}`} />
          {PARTS.map(({ n }) => {
            const c = content[n as PartNo];
            const foot = n === 2 && !sorting?.confirmed ? c.foot : undefined;
            return (
              <PartFrame
                key={n}
                n={n as PartNo}
                heading={c.heading}
                line={c.line}
                phone
                foot={foot}
                headingId={n === 2 ? "pr-sort-h" : n === 3 ? "pr-sim-h" : undefined}
              >
                {c.body}
              </PartFrame>
            );
          })}
        </div>
        {sheet}
      </div>
    );
  }

  const c = content[part];
  return (
    <div className="ck">
      {taskbar}
      {bar}
      <div className="ck-grid">
        <nav className="ck-rail" aria-label={C.rail}>
          <ol>
            {PARTS.map(({ n, label }) => {
              const no = n as PartNo;
              const now = no === part;
              const ok = isDone(no) && !now;
              // The Send it row's line ("One last look, then submit") sits beside its button as its description, not
              // inside it, so "Submit" names one button on the page and the button's name is its visible words
              // (BLD-C130; J-SHARE/11, J-RECOVER/12–14 find Submit by name; WCAG 2.5.3).
              const send = no === 7;
              return (
                <li key={n}>
                  <button
                    type="button"
                    className={["ck-rb", now ? "now" : "", ok ? "done" : "", attention[no] ? "warn" : ""]
                      .filter(Boolean)
                      .join(" ")}
                    aria-current={now ? "step" : undefined}
                    aria-describedby={send ? railStatusId : undefined}
                    onClick={() => go(no)}
                  >
                    <span className="ck-rn" aria-hidden={ok || attention[no] ? true : undefined}>
                      {ok ? <IconTick size={12} /> : attention[no] ? "!" : n}
                    </span>
                    {/* The tick and the "!" are drawn only; a screen reader hears ", done" (the task bar's words)
                        or the part's number, as the board names the button ("2 Sorting Suggested, …"). */}
                    {attention[no] && !ok ? <span className="vh">{`${n} `}</span> : ok ? null : " "}
                    <span className="ck-rl">{label}</span>
                    {ok ? <span className="vh">{C.done}</span> : null}
                    {send ? (
                      <span className="ck-rs ck-rs-gap" aria-hidden="true" />
                    ) : (
                      <>
                        {" "}
                        <span className="ck-rs">{rail[no]}</span>
                      </>
                    )}
                  </button>
                  {send ? (
                    <span className="ck-rs ck-rs-over" id={railStatusId}>
                      {rail[no]}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </nav>
        <div className="ck-stage panel" data-dir={dir > 0 ? "fwd" : "back"}>
          <div key={part} className="ck-slide">
            <PartFrame
              ref={heading}
              n={part}
              heading={c.heading}
              line={c.line}
              foot={part === 7 ? undefined : c.foot}
            >
              {c.body}
            </PartFrame>
          </div>
        </div>
      </div>
      {sheet}
    </div>
  );
}
