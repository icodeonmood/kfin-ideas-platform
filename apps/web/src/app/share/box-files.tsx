"use client";
/**
 * C-PROMPT.attach in the prompt box (DEC-124, walk item WF-01; BLD-C212 to BLD-C215): Home (S-03), Share a problem
 * (S-04) and the draft page (S-04B). The "+" (`AttachButton`, first in the tool row) opens the picker drawn on the Home
 * board (`attachments=Picker open`, C-FILE.uploader): the drop area with "browse", "Choose a folder", and the link
 * field. Each file goes through `POST /api/files` with the draft's id, so DEC-107's checks run unchanged (the virus
 * scan, then the personal-details check; a file with a detail found opens only for the sharer, the review desk and the
 * Ones Committee). Each shows as a row inside the box (C-FILE.row) with "Remove {name}" (Home.md), which deletes it
 * (`DELETE /api/files/:id`). The rows belong to the draft, not to one message: they stay in the box until removed,
 * travel with the draft to the draft page, and show again on Check it under Proof (BLD-C214). A page with no draft yet
 * makes it on the first file (`resolveDraft`), once. The rows and their checks are Check it's own (`useProof`), so a
 * file behaves the same in both places. Links are kept as typed and never fetched (BLD-E001).
 */
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

import { AttachButton } from "@/components/ui/attach-button";
import { Button } from "@/components/ui/button";
import { FileList, FileRemove, FileRow } from "@/components/ui/file";
import { FilePicker, PICKER_COPY } from "@/components/ui/file-picker";
import type { FileItem, UploadConfig } from "@/lib/contracts";

import { api, type Call } from "./[id]/check/client";
import { CHECK_COPY } from "./[id]/check/copy";
import { rowView, type ProofItem } from "./[id]/check/model";
import { useProof } from "./[id]/check/use-proof";

/** The Home board's words for the picker and the rows (reference/copy/Home.md, `attachments`). */
export const BOX_FILES_COPY = {
  // The picker's own words live with lane D's shared picker (BLD-D031); the same keys, nothing renamed
  dropTitle: PICKER_COPY.dropTitle,
  browse: PICKER_COPY.browse,
  folder: PICKER_COPY.folder,
  folderLine: PICKER_COPY.folderLine,
  linkInput: PICKER_COPY.linkInput,
  addLink: PICKER_COPY.addLink,
  linkLine: PICKER_COPY.linkLine,
  /** NOT DRAWN: the list's name for screen readers (listed in BUILD_LOG "to confirm later", BLD-C215). */
  rows: "Your files and links",
  removeOf: CHECK_COPY.proof.removeOf,
  /** To confirm later (HR, DEC-123; BLD-C224): the status line's words. "Checked" and the row's own lines are the
   * boards' (C-FILE.row); "added" is new. */
  added: (name: string) => `${name} added`,
  addedMany: (n: number) => `${n} files added`,
  rowNow: (name: string, line: string) => `${name}: ${line}`,
  /** To confirm later (HR, DEC-123; BLD-C224): nothing left to add once names starting with "." are left out. */
  onlyDotFiles: "Nothing was added. Files whose names start with a dot are left out.",
  /** To confirm later (HR, DEC-123; BLD-C224): a folder dropped where the browser gives no way to read it. */
  useFolder: PICKER_COPY.useFolder,
} as const;

/** The limit before `GET /api/config/uploads` answers: the web edge's own ceiling; the worker checks the real one. */
const LIMIT_BEFORE_CONFIG_MB = 25;

const passThrough = <T,>(p: Promise<Call<T>>) => p;

/** The person's files as the draft read sends them: the box holds those not sent with a message (`message_id`, from
 * an email or a later channel), which show with their message instead. */
export function boxFilesOf(files: readonly FileItem[] | undefined): FileItem[] {
  return (files ?? []).filter((f) => !(f as { message_id?: string }).message_id);
}

export type BoxFiles = {
  /** The "+" for the tool row (C-PROMPT.anatomy/2). */
  button: ReactNode;
  /** The picker, open under the words; null when closed. */
  picker: ReactNode;
  /** The rows inside the box; null when there are none. */
  rows: ReactNode;
  /** The draft's files as read (S-04B), put in the box. */
  load(files: FileItem[]): void;
  /** Every upload still on its way has answered (the page is about to move on). */
  settle(): Promise<void>;
};

export function useBoxFiles({
  draftId,
  resolveDraft,
}: {
  draftId: string | null;
  /** Makes the draft when there is none yet (Home, an empty Share a problem); the same promise for every file. */
  resolveDraft?: () => Promise<string | null>;
}): BoxFiles {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<UploadConfig | null>(null);
  const limitMb = config?.limit_mb ?? LIMIT_BEFORE_CONFIG_MB;
  const proof = useProof(draftId, passThrough, limitMb, resolveDraft);
  const ids = useId();
  const pickerId = `${ids}-pick`;
  const plus = useRef<HTMLSpanElement>(null);
  const [note, setNote] = useState<string | null>(null);
  const quiet = useRef(false);
  const status = useStatusLine(proof.proof, limitMb, quiet);
  const proofLoad = proof.load;
  // A draft's files put back in the box (S-04B) are not news: the status line stays as it was.
  const load = useCallback(
    (files: FileItem[]) => {
      quiet.current = true;
      proofLoad(files);
    },
    [proofLoad],
  );

  // The one limit, type list and help line (C-FILE.uploader/1, BLD-E007), read when the picker first opens.
  useEffect(() => {
    if (!open || config) return;
    let gone = false;
    void api.uploads().then((r) => {
      if (!gone && r.ok && r.body && typeof r.body.limit_mb === "number") setConfig(r.body);
    });
    return () => {
      gone = true;
    };
  }, [open, config]);

  const close = (focus: boolean) => {
    setOpen(false);
    setNote(null);
    if (focus) requestAnimationFrame(() => plus.current?.querySelector("button")?.focus());
  };

  const addFiles = (files: File[]) => {
    // A folder's own entries for the system (".DS_Store" and the like) are not the person's files.
    const kept = files.filter((f) => !f.name.startsWith("."));
    if (!kept.length) {
      setNote(files.length ? BOX_FILES_COPY.onlyDotFiles : null); // the picker stays open and says why
      return;
    }
    proof.addFiles(kept);
    close(true);
  };

  // WCAG 2.4.3: Escape closes the picker from anywhere in the "+" or the picker, the "+" itself included, and the
  // focus goes back to "+". The status line lives here too: outside the list, so a row is never found twice.
  const button = (
    <span
      ref={plus}
      className="attach-w"
      onKeyDown={(e) => {
        if (e.key !== "Escape" || !open) return;
        e.stopPropagation();
        close(true);
      }}
    >
      <AttachButton
        aria-expanded={open}
        aria-controls={open ? pickerId : undefined}
        onClick={() => {
          setNote(null);
          setOpen((o) => !o);
        }}
      />
      <span className="vh" role="status">
        {status}
      </span>
    </span>
  );

  const picker = open ? (
    <FilePicker
      id={pickerId}
      className="cpick"
      help={config?.help_text ?? null}
      linkHelp={BOX_FILES_COPY.linkLine}
      note={note}
      onNote={setNote}
      onFiles={addFiles}
      onLinks={async (links) => {
        const out = await proof.addLinks(links);
        if (!out.left.length && !out.problem) close(true);
        return out;
      }}
      onClose={() => close(true)}
    />
  ) : null;

  const rows = proof.proof.length ? (
    <Rows
      items={proof.proof}
      limitMb={limitMb}
      onRetry={(key) => void proof.retryFile(key)}
      onRemove={(key) => void proof.removeFile(key)}
    />
  ) : null;

  return { button, picker, rows, load, settle: proof.settleUploads };
}

function Rows({
  items,
  limitMb,
  onRetry,
  onRemove,
}: {
  items: ProofItem[];
  limitMb: number;
  onRetry(key: string): void;
  onRemove(key: string): void;
}) {
  return (
    <div className="cfiles">
      {/* Lane D's compact FileList without its aria-live: the status line says what changed (BLD-C224, BLD-D030).
          Compact draws the rows as the box always has, and a row with a message takes its own line without :has()
          (BLD-C244). */}
      <FileList label={BOX_FILES_COPY.rows} live={false} compact>
        {items.map((p) => {
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
              waiting={v.waiting}
            >
              {v.actions.includes("retry") ? (
                <Button variant="text-blue" onClick={() => onRetry(p.key)}>
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

/**
 * The status line (WCAG 4.1.3, BLD-C224): one short line for what last changed in the rows, "{name} added", then
 * "{name}: Checked" or the row's own line, in place of the whole list being read again. Empty on page load: the
 * rows already there when the box first draws them, or when a draft's files are put back (`load`), say nothing.
 * A removed row's line goes with it.
 */
function useStatusLine(items: ProofItem[], limitMb: number, quietRef: { current: boolean }): string {
  const seen = useRef<Map<string, string> | null>(null);
  const [line, setLine] = useState("");
  useEffect(() => {
    const now = new Map(items.map((p) => [p.key, lineOf(p, limitMb)] as const));
    const before = seen.current;
    seen.current = now;
    if (before === null || quietRef.current) {
      quietRef.current = false; // the first draw, or `load`
      return;
    }
    setLine((was) => nextLine(items, before, now) ?? was);
  }, [items, limitMb, quietRef]);
  return line;
}

/** The new line, or null to keep the one there: a row added, then a row whose words changed, then a row removed
 * (its name leaves the line). */
function nextLine(items: ProofItem[], before: Map<string, string>, now: Map<string, string>): string | null {
  const added = items.filter((p) => !before.has(p.key));
  if (added.length > 1) return BOX_FILES_COPY.addedMany(added.length);
  if (added.length === 1) return BOX_FILES_COPY.added(nameOf(added[0]!));
  const changed = items.filter((p) => now.get(p.key) && before.get(p.key) !== now.get(p.key));
  const last = changed[changed.length - 1];
  if (last) return BOX_FILES_COPY.rowNow(nameOf(last), now.get(last.key)!);
  if ([...before.keys()].some((k) => !now.has(k))) return "";
  return null;
}

const nameOf = (p: ProofItem) => p.item?.name ?? p.name;

/** The row's own words, as it shows them: its status ("Checked") or its line ("Didn’t upload. …"). */
function lineOf(p: ProofItem, limitMb: number): string {
  const v = rowView(p, limitMb);
  return v.message?.text || v.statusText || "";
}
