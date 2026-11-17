"use client";

/**
 * S-06B "Edit after sharing", `/ideas/:id/edit` (L-SUBMIT.edit; J-RECOVER/7–10 and /15 on S-06B, J-SHARE's
 * S-06 → S-06B → S-06). The same content as Check it on one page: your problem with its hidden details, the sorting,
 * anything that shows it, and your fix; the declaration beside "Save changes"; and the side panel "What happens when
 * you save". Nothing reaches anyone else until Save (L-SUBMIT.edit/2): the words, the sorting and the fix wait on
 * this page and go in one `PATCH`, which makes a new version only when something changed. Files and links are
 * checked as they are added, and "Show it" acts at once, as on Check it (BLD-C161). Files and links added or removed
 * here still count as unsaved changes: Cancel confirms and takes the added ones away again, and Save records them in
 * the version (`files`).
 *
 * After Save the page reads "Saved. The review desk will see the latest version." with "Back to your idea" to S-06
 * (BLD-C160). If the review desk opens the idea meanwhile, Save is refused (`edit_window_closed`): the changes stay on
 * the page with "Open the conversation", which carries the changed words into the message box (S-06B.rules/2,
 * BLD-C165). Desktop: the task bar, one column and the side panel. Phone: the same sections in one column, the bar's
 * "Cancel" ("Back to your idea" once saved), and "Save changes" in the dock (S-06B.rules/5).
 *
 * Leaving with unsaved changes (BLD-C163): Cancel, the bar's close and any other link on the page (the side bar, Back)
 * first show the in-place confirm; the next one leaves without them. Closing or reloading the tab asks the browser's
 * own question.
 *
 * The parts are S-05's (share/[id]/check): WordsBody, HiddenTile, SortingBody, ProofBody, FixPartBody and FixSheet,
 * with the edit context's props. No words are logged (non-negotiable 3).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { IconTick } from "@/components/shell/icons";
import { Taskbar, type SaveState } from "@/components/shell/taskbar";
import { Button, ButtonLink, buttonClass } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { Loading, SkeletonRows } from "@/components/ui/skeleton";
import { putPrefill } from "@/components/convo/prefill";
import type {
  ApiError,
  ConfigResponse,
  EditPageResponse,
  EditSaveResponse,
  HiddenDetail,
  ShowReason,
  UploadConfig,
} from "@/lib/contracts";

import { api, type Call } from "@/app/share/[id]/check/client";
import { useOnline, usePhone } from "@/app/share/[id]/check/check-it";
import { CHECK_COPY } from "@/app/share/[id]/check/copy";
import { FixPartBody, FixSheet, typedAnything } from "@/app/share/[id]/check/fix";
import { HiddenTile } from "@/app/share/[id]/check/hidden";
import { EMPTY_FIX, fixFormFrom, fixReady, oneLine, type FixForm } from "@/app/share/[id]/check/model";
import { SortingBody, WordsBody } from "@/app/share/[id]/check/parts";
import { ProofBody } from "@/app/share/[id]/check/proof";
import { useProof } from "@/app/share/[id]/check/use-proof";

import { EDIT_COPY } from "./copy";
import {
  HOW_MIN,
  NO_FILES,
  addedRows,
  afterSave,
  baseAfter,
  editPatch,
  filesDelta,
  initialState,
  isDirty,
  placeOf,
  prefillText,
  rebase,
  sortingView,
  type EditState,
  type ErrorPlace,
  type FilesDelta,
  type SortingPending,
} from "./model";

import "@/app/share/[id]/check/check.css";
import "./edit.css";

const C = CHECK_COPY;
const E = EDIT_COPY;
const DEFAULT_LIMIT_MB = 25;

type Refusal = ApiError["error"] & {
  to?: string;
  opened_by_desk_at?: string;
  version?: string;
  text?: string;
};

/** After Save: the server's words, and whether it made a version (L-SUBMIT.edit/4). */
type Outcome =
  | { kind: "none" }
  | { kind: "saved"; message: string }
  | { kind: "closed"; message: string; to: string }
  | { kind: "failed"; message: string };

/** A file's own calls are not the page's save status: they act at once. The rows count as changes (`filesDelta`). */
const passThrough = <T,>(p: Promise<Call<T>>) => p;

function stateFrom(page: EditPageResponse): EditState {
  return initialState(page, EMPTY_FIX, fixFormFrom(page.fix));
}

const fileIds = (p: EditPageResponse) => p.files.map((f) => f.id);

/** Where a click on a link takes the person, or null when it is not a page change this page guards (a new tab, a
 * download, a modified click, another site, the same page, or a link marked to go on as it is). */
function leavingTo(e: globalThis.MouseEvent): string | null {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return null;
  const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a || (a.target && a.target !== "_self") || a.hasAttribute("download") || "edGo" in a.dataset)
    return null;
  const to = new URL(a.href, window.location.href);
  if (to.origin !== window.location.origin) return null;
  if (to.pathname === window.location.pathname && to.search === window.location.search) return null;
  return `${to.pathname}${to.search}${to.hash}`;
}

export function EditIdea({
  ideaId,
  config: initialConfig,
  blackout = false,
}: {
  ideaId: string;
  config: ConfigResponse | null;
  /** `files.blackout` (DEC-107, BLD-C064): "Hide it for me" on a file is offered only while it is on. */
  blackout?: boolean;
}) {
  const online = useOnline();
  const phone = usePhone();
  const router = useRouter();

  const [page, setPage] = useState<EditPageResponse | null>(null);
  const [loadFailed, setLoadFailed] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(initialConfig);
  const [uploads, setUploads] = useState<UploadConfig | null>(null);
  const [state, setState] = useState<EditState | null>(null);
  const [hidden, setHidden] = useState<HiddenDetail[]>([]);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "none" });
  const [errors, setErrors] = useState<Partial<Record<ErrorPlace, string>>>({});
  const [confirmCancel, setConfirmCancel] = useState(false);
  /** The file and link IDs the page started from (load, or the last save): what it added or removed is counted
   * against them. */
  const [fileBase, setFileBase] = useState<string[]>([]);
  /** The declaration changed while the page was open: the phone shows the server's words, not its own short line. */
  const [declChanged, setDeclChanged] = useState(false);
  /** Set once the person has chosen to leave, so neither the link guard nor the browser asks again. */
  const leaving = useRef(false);
  /** Leaving could not take away a file this page added: the person has its row's words, so the next link leaves. */
  const discardFailed = useRef(false);
  const confirmRef = useRef<HTMLParagraphElement>(null);
  const sortingRef = useRef<HTMLElement>(null);
  const ids = useId();

  const limits = uploads ?? config?.uploads ?? null;
  const limitMb = limits?.limit_mb ?? DEFAULT_LIMIT_MB;
  const proof = useProof({ idea_id: page?.id ?? ideaId }, passThrough, limitMb);
  const loadProof = proof.load;

  // --- Loading ------------------------------------------------------------------------------------------------------

  /** The page as the server sent it. After a save the file rows stay as they are: files never wait for Save, and a
   * row that is still uploading, or failed in this browser, must not vanish. A save passes what it sent, so anything
   * changed while it was on its way stays as the person left it (`rebase`). */
  const take = useCallback(
    (p: EditPageResponse, opts: { files?: boolean; sent?: EditState } = {}) => {
      setPage(p);
      const fresh = stateFrom(p);
      const sent = opts.sent;
      setState((cur) => (sent && cur ? rebase(sent, cur, fresh) : fresh));
      setHidden(p.hidden);
      if (opts.files !== false) {
        loadProof(p.files as Parameters<typeof loadProof>[0]);
        setFileBase(fileIds(p));
      }
    },
    [loadProof],
  );

  const fetchAll = useCallback(
    () =>
      Promise.all([
        api.editPage(ideaId),
        initialConfig ? Promise.resolve(null) : api.config(),
        api.uploads(),
      ]),
    [ideaId, initialConfig],
  );

  const apply = useCallback(
    ([p, cfg, up]: Awaited<ReturnType<typeof fetchAll>>) => {
      if (!p.ok || !p.body) {
        setLoadFailed((!p.ok && p.error?.message) || C.failed);
        return;
      }
      setLoadFailed(null);
      take(p.body);
      if (cfg && cfg.ok) setConfig(cfg.body);
      if (up.ok && up.body && typeof up.body.limit_mb === "number") setUploads(up.body);
    },
    [take],
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

  // --- Changes that wait for Save --------------------------------------------------------------------------------

  /** A new change after the confirm asks again before leaving (BLD-C163). */
  const unconfirm = () => {
    setConfirmCancel(false);
    discardFailed.current = false;
  };

  const change = (next: (s: EditState) => EditState) => {
    setState((s) => (s ? next(s) : s));
    unconfirm();
    // A new change starts a new round: the last save's words no longer describe the page. A refusal that the
    // desk opened it stays: Save cannot work again here.
    setOutcome((o) => (o.kind === "closed" ? o : { kind: "none" }));
  };

  const saveWord = async (key: "title" | "summary" | "often", value: string) => {
    change((s) => ({ ...s, [key]: value }));
    setErrors((e) => ({ ...e, words: undefined }));
    return true;
  };

  const changeSorting = (patch: SortingPending) => {
    change((s) => ({ ...s, sorting: { ...s.sorting, ...patch } }));
    setErrors((e) => ({ ...e, sorting: undefined }));
  };

  // --- Hidden details: "Show it" acts at once, as on Check it (C-HIDDEN, L-HIDE.rules/6) ---------------------------

  const updateHidden = (h: HiddenDetail) => setHidden((list) => list.map((x) => (x.id === h.id ? h : x)));

  const showHidden = async (id: string, reason: ShowReason): Promise<boolean | string> => {
    if (!page) return false;
    const r = await api.showHidden(page.ref, id, reason);
    if (r.ok && r.body) {
      updateHidden(r.body);
      return true;
    }
    // 403: "The review desk hid this, so it stays hidden." The server's words, under the tile.
    return (!r.ok && r.status === 403 && r.error?.message) || false;
  };

  const hideAgain = async (id: string) => {
    if (!page) return false;
    const r = await api.hideAgain(page.ref, id);
    if (r.ok && r.body) updateHidden(r.body);
    return r.ok;
  };

  // --- The fix: kept on this page until Save (S-05.fix in the edit context) ------------------------------------------

  const addFix = async (form: FixForm) => {
    if (form.how.trim().length < HOW_MIN) return { field: "how" as const, message: C.sheet.howNeeded };
    change((s) => ({
      ...s,
      fix: {
        part: { kind: "added", line: C.fix.included(fixReady(form)), fixLine: oneLine(form.how) },
        form,
        touched: true,
      },
    }));
    setErrors((e) => ({ ...e, fix: undefined }));
    setSheetOpen(false);
    return null;
  };

  const keepFix = async (form: FixForm) => {
    setSheetOpen(false);
    // An added fix stays as it was; "Close, and keep what you wrote" keeps a fix that is not added yet, on this page.
    if (!state || state.fix.part.kind === "added" || !typedAnything(form)) return null;
    change((s) => ({ ...s, fix: { ...s.fix, part: { kind: "started" }, form } }));
    return null;
  };

  const removeFix = () => {
    change((s) => ({ ...s, fix: { part: { kind: "none" }, form: EMPTY_FIX, touched: true } }));
    setErrors((e) => ({ ...e, fix: undefined }));
  };

  // --- Save --------------------------------------------------------------------------------------------------------

  const view = page && state ? sortingView(page.sorting, state.sorting) : null;
  const files: FilesDelta = page ? filesDelta(fileBase, proof.proof) : NO_FILES;
  const dirty = page && state ? isDirty(page, state, files) : false;
  const closed = outcome.kind === "closed";

  const save = async () => {
    if (!page || !state || !view || saving || closed) return;
    setErrors({});
    if (!view.complete) {
      // S-06B.rules/3: the card already says what to do ("Confirm these, …"); nothing is sent, and focus goes there.
      sortingRef.current?.focus();
      return;
    }
    setSaving(true);
    const sent = state;
    const sentFiles = files;
    const r = await api.saveEdit(page.ref, {
      ...editPatch(page, sent, sentFiles),
      declaration_version: page.declaration.version,
    });
    if (r.ok) {
      await saved(r.body, sent, sentFiles);
      setSaving(false);
      return;
    }
    setSaving(false);
    refused(r.status, r.error as Refusal | null);
  };

  const saved = async (body: EditSaveResponse, sent: EditState, sentFiles: FilesDelta) => {
    if (body.version) setSavedAt(body.version.at);
    // The files and links that save carried are now where the page starts from.
    setFileBase((b) => baseAfter(b, sentFiles));
    // Read the page again: the server keeps the masked copy of new words, and may have hidden a detail in them.
    const again = await api.editPage(ideaId);
    if (again.ok && again.body) take(again.body, { files: false, sent });
    else if (page) {
      // The page could not be read again: what was sent is now what the page compares against.
      const next = afterSave(page, sent);
      setPage(next.page);
      setState((cur) => (cur ? rebase(sent, cur, next.state) : next.state));
    }
    setConfirmCancel(false);
    setOutcome({ kind: "saved", message: body.message || E.saved });
  };

  const refused = (status: number, err: Refusal | null) => {
    if (err?.code === "edit_window_closed") {
      // S-06B.rules/2: the changes stay below; they go to the review desk as a message instead.
      setOutcome({
        kind: "closed",
        message: err.message || C.failed,
        to: err.to || `/ideas/${encodeURIComponent(page?.ref ?? ideaId)}/conversation`,
      });
      return;
    }
    if (err?.code === "declaration_changed" && page && err.version && err.text) {
      setPage({ ...page, declaration: { version: err.version, text: err.text } });
      setDeclChanged(true);
    }
    const message = (status !== 0 && status < 500 && err?.message) || C.failed;
    const place = placeOf(err?.field);
    if (place === "save") setOutcome({ kind: "failed", message });
    else setErrors({ [place]: message });
  };

  // --- Leaving with unsaved changes (S-06B.layout/7, BLD-C163) ------------------------------------------------------

  /** Leaving without saving takes away again the files and links this page added (they acted at once): a row still
   * uploading is waited for, then its file deleted. True when every one of them is gone; one that cannot be removed
   * stays on the page with its row's words under it, as after a Remove that failed. Removed ones stay removed: a
   * removal cannot be undone (BLD-C161). */
  const discard = async (): Promise<boolean> => {
    const rows = addedRows(fileBase, proof.proof);
    const gone = await Promise.all(rows.map((r) => proof.removeFile(r.key, { wait: true })));
    return gone.every(Boolean);
  };

  // Any link on the page (Cancel, the bar's close, the side bar, Back) shows the in-place confirm first while there
  // are unsaved changes; the next one leaves without them. Links that open elsewhere, and "Open the conversation"
  // after a refusal (it carries the words on), go as they are.
  useEffect(() => {
    if (!dirty) return;
    const onClick = (e: globalThis.MouseEvent) => {
      if (leaving.current) return;
      const to = leavingTo(e);
      if (!to) return;
      if (!confirmCancel) {
        e.preventDefault();
        e.stopPropagation();
        setConfirmCancel(true);
        return;
      }
      leaving.current = true;
      // Nothing to take away, or the person already has the words of a file that would not go: the link goes as it is.
      if (discardFailed.current || !addedRows(fileBase, proof.proof).length) return;
      e.preventDefault();
      e.stopPropagation();
      void discard().then((gone) => {
        if (gone) {
          router.push(to);
          return;
        }
        // A file this page added is still on the idea, and the review desk could open it: stay, with the row's own
        // words under it, brought into view; the next link leaves.
        discardFailed.current = true;
        leaving.current = false;
        window.setTimeout(
          () => document.querySelector(".ck-proof")?.scrollIntoView?.({ block: "nearest" }),
          0,
        );
      });
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  });

  // Closing or reloading the tab with unsaved changes: the browser's own question.
  useEffect(() => {
    if (!dirty) return;
    const onLeave = (e: BeforeUnloadEvent) => {
      if (leaving.current) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, [dirty]);

  // The confirm is announced; it is also brought into view when a link far from the foot asked for it.
  useEffect(() => {
    if (confirmCancel) confirmRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [confirmCancel]);

  /** S-06B.rules/2: "Open the conversation" carries the changed words into the message box (BLD-C165). */
  const carryWords = () => {
    if (!page || !state) return;
    putPrefill(
      page.ref,
      prefillText(page, state, {
        title: C.words.title,
        summary: C.words.summary,
        often: C.words.often,
        how: C.sheet.how,
      }),
    );
    leaving.current = true;
  };

  // --- What the page shows ---------------------------------------------------------------------------------------

  if (loadFailed) {
    return (
      <div className="ck ck-loading">
        <FieldMsg>{loadFailed}</FieldMsg>
        <Button
          variant="line"
          onClick={() => {
            setLoadFailed(null);
            void fetchAll().then(apply);
          }}
        >
          {C.retry}
        </Button>
      </div>
    );
  }
  if (!page || !state || !view) {
    return (
      <div className="ck ck-loading">
        <Loading what={E.heading}>
          <SkeletonRows what={E.heading} rows={4} />
        </Loading>
      </div>
    );
  }

  const back = page.bar.back;
  const conversation = `/ideas/${encodeURIComponent(page.ref)}/conversation`;
  const taskSave: SaveState = saving ? "saving" : dirty ? (online ? "changed" : "offline") : "saved";
  const isSaved = outcome.kind === "saved" && !dirty;
  // PhoneEdit.md: the phone's bar closes with "Cancel" until the page is saved, then "Back to your idea".
  const closeLabel = phone && !isSaved ? E.cancel : back.label || E.back;

  const taskbar = (
    <Taskbar
      title={page.bar.title}
      step="check"
      steps={false}
      save={taskSave}
      savedAt={savedAt}
      closeHref={back.to}
      closeLabel={closeLabel}
      extra={<p className="editline">{page.bar.line}</p>}
    />
  );

  // The window had closed before the page opened (L-SUBMIT.edit/5): the server's line and the way to the desk.
  if (!page.window.open) {
    return (
      <div className="ck ed">
        {taskbar}
        <div className="ed-closed">
          <h1 className="h1">{E.heading}</h1>
          {page.window.line ? (
            <p className="bmsg info" role="status">
              {page.window.line}
            </p>
          ) : null}
          <div className="ed-closed-acts">
            <ButtonLink variant="primary" href={conversation}>
              {E.conversation}
            </ButtonLink>
            <Link href={back.to} className={buttonClass("text")}>
              {back.label || E.back}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const controls = config?.sorting.controls;
  const side = phone
    ? page.side
        .slice(0, 2)
        .map((s) => (s.when.startsWith("At the latest") ? { ...s, line: E.phone.sideClose } : s))
    : page.side;
  const opt = <span className="opt">{E.optional}</span>;

  const sections = (
    <>
      <section className="ed-sec" aria-labelledby={`${ids}-w`}>
        <div className="ed-sech">
          <h2 className="h2" id={`${ids}-w`}>
            {E.words.heading}
          </h2>
          {phone ? null : <p className="meta">{E.words.line}</p>}
        </div>
        <div className="ed-words panel">
          <WordsBody
            values={{ title: state.title, summary: state.summary, often: state.often }}
            attached={[]}
            onSave={saveWord}
            onAttached={() => undefined}
            phone={phone}
            hidden={<HiddenTile details={hidden} onShow={showHidden} onHide={hideAgain} phone={phone} />}
          />
          {errors.words ? <FieldMsg>{errors.words}</FieldMsg> : null}
        </div>
      </section>

      <section
        className="ed-sec"
        aria-labelledby={`${ids}-s`}
        ref={sortingRef}
        tabIndex={-1}
        data-part="sorting"
      >
        <div className="ed-sech">
          <h2 className="h2" id={`${ids}-s`}>
            {E.sorting.heading}
          </h2>
          {phone ? null : <p className="meta">{E.sorting.line}</p>}
        </div>
        {controls ? (
          <SortingBody
            sorting={view}
            controls={controls}
            onChange={(patch) => changeSorting(patch as SortingPending)}
            unconfirmedTried
            error={errors.sorting ?? null}
          />
        ) : (
          <SkeletonRows what={E.sorting.heading} rows={4} />
        )}
      </section>

      <section className="ed-sec" aria-labelledby={`${ids}-p`}>
        <h2 className="h2" id={`${ids}-p`}>
          {E.proof.heading} {opt}
        </h2>
        <ProofBody
          items={proof.proof}
          limitMb={limitMb}
          help={limits?.help_text || C.proof.dropHelp}
          accept={limits?.types?.length ? limits.types.join(",") : undefined}
          onFiles={(f) => {
            unconfirm();
            proof.addFiles(f);
          }}
          onLinks={(links) => {
            unconfirm();
            return proof.addLinks(links);
          }}
          onRetry={(k) => void proof.retryFile(k)}
          onHide={(k) => void proof.hideFile(k)}
          onRemove={(k) => {
            unconfirm();
            void proof.removeFile(k);
          }}
          showHelps={!phone}
          canHide={blackout}
          edit={
            phone
              ? {
                  links: E.proof.links,
                  linkInput: E.phone.linkInput,
                  addLink: E.phone.addLink,
                  pick: E.phone.pick,
                }
              : { links: E.proof.links, linkInput: E.proof.linkInput, addLink: E.proof.addLink }
          }
        />
      </section>

      <section className="ed-sec" aria-labelledby={`${ids}-f`}>
        <h2 className="h2" id={`${ids}-f`}>
          {E.fix.heading} {opt}
        </h2>
        <FixPartBody
          part={state.fix.part}
          onOpen={() => {
            setErrors((e) => ({ ...e, fix: undefined }));
            setSheetOpen(true);
          }}
          onRemove={removeFix}
          removing={false}
          error={errors.fix ?? null}
          words={{ title: E.fix.title, line: E.fix.line }}
        />
      </section>
    </>
  );

  const sidePanel = (
    <section className="ed-next panel" aria-labelledby={`${ids}-n`}>
      <h2 className="h3" id={`${ids}-n`}>
        {E.side}
      </h2>
      <ol className="ed-nl">
        {side.map((s, i) => (
          <li key={s.when} className={i === 0 ? "on" : undefined}>
            <p className="ed-nt">{s.when}</p>
            <p className="ed-nd">{s.line}</p>
          </li>
        ))}
      </ol>
    </section>
  );

  // The saved line's live region is on the page before its words, so they are announced (WCAG 4.1.3).
  const live = (
    <div className="ed-live" role="status">
      {outcome.kind === "saved" ? (
        <p className="bmsg ok">
          <IconTick size={14} />
          <span>{outcome.message}</span>
        </p>
      ) : null}
    </div>
  );

  const alert =
    outcome.kind === "closed" ? (
      <div className="bmsg bad" role="alert">
        <span>{outcome.message}</span>
        <Link href={outcome.to} className="tb" data-ed-go="" onClick={carryWords}>
          {E.conversation}
        </Link>
      </div>
    ) : outcome.kind === "failed" ? (
      <p className="bmsg bad" role="alert">
        {outcome.message}
      </p>
    ) : null;

  const cancel = isSaved ? null : (
    <Link href={back.to} className={buttonClass("text")}>
      {E.cancel}
    </Link>
  );

  const foot = (
    <div className={phone ? "dock ed-dock" : "ed-foot"}>
      {confirmCancel ? (
        <p className="bmsg warn ed-confirm" role="alert" ref={confirmRef}>
          <strong>{E.cancelConfirm.lead}.</strong> {E.cancelConfirm.line}
        </p>
      ) : null}
      {live}
      {alert}
      <p className="decl">{phone && !declChanged ? E.phone.declaration : page.declaration.text}</p>
      <div className="ed-acts">
        {cancel}
        <Button busy={saving} busyLabel={E.saving} disabled={closed} onClick={() => void save()}>
          {E.save}
        </Button>
      </div>
    </div>
  );

  const sheet = (
    <FixSheet
      open={sheetOpen}
      initial={state.fix.form}
      onCancel={() => setSheetOpen(false)}
      onKeep={keepFix}
      onAdd={addFix}
    />
  );

  return (
    <div className={phone ? "ck ed ed-phone" : "ck ed"}>
      {taskbar}
      <div className="ed-page">
        <div className="ed-main">
          <h1 className="h1 ed-h">{E.heading}</h1>
          <p className="ck-line">{E.line}</p>
          {sections}
          {phone ? sidePanel : null}
          {foot}
        </div>
        {phone ? null : <aside className="ed-aside">{sidePanel}</aside>}
      </div>
      {sheet}
    </div>
  );
}
