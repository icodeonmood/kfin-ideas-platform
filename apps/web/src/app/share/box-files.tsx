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
import {
  useEffect,
  useId,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { AttachButton } from "@/components/ui/attach-button";
import { IconClose, IconFolder, IconLink } from "@/components/compose/icons";
import { Button } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { DropArea, FileList, FileRow } from "@/components/ui/file";
import type { FileItem, UploadConfig } from "@/lib/contracts";

import { api, type Call } from "./[id]/check/client";
import { CHECK_COPY } from "./[id]/check/copy";
import { rowView, splitLinks, type ProofItem } from "./[id]/check/model";
import { useProof } from "./[id]/check/use-proof";

/** The Home board's words for the picker and the rows (reference/copy/Home.md, `attachments`). */
export const BOX_FILES_COPY = {
  dropTitle: "Drop files or a folder here, or",
  browse: "browse",
  folder: "Choose a folder",
  folderLine: "Tap the folder to add a whole folder.",
  linkInput: "Or paste a link to a page, file or idea",
  addLink: "Add link",
  linkLine: "SharePoint, Teams and 1% Club links are marked internal. Anything else is marked external.",
  /** NOT DRAWN: the list's name for screen readers (listed in BUILD_LOG "to confirm later", BLD-C215). */
  rows: "Your files and links",
  removeOf: CHECK_COPY.proof.removeOf,
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
    if (focus) requestAnimationFrame(() => plus.current?.querySelector("button")?.focus());
  };

  const addFiles = (files: File[]) => {
    // A folder's own entries for the system (".DS_Store" and the like) are not the person's files.
    const kept = files.filter((f) => !f.name.startsWith("."));
    if (!kept.length) return;
    proof.addFiles(kept);
    close(true);
  };

  const button = (
    <span ref={plus} className="attach-w">
      <AttachButton
        aria-expanded={open}
        aria-controls={open ? pickerId : undefined}
        onClick={() => setOpen((o) => !o)}
      />
    </span>
  );

  const picker = open ? (
    <Picker
      id={pickerId}
      help={config?.help_text ?? null}
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

  return { button, picker, rows, load: proof.load, settle: proof.settleUploads };
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
      <FileList label={BOX_FILES_COPY.rows}>
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
              <button
                type="button"
                className="cfile-x"
                aria-label={BOX_FILES_COPY.removeOf(name)}
                title={BOX_FILES_COPY.removeOf(name)}
                onClick={() => onRemove(p.key)}
              >
                <IconClose />
              </button>
            </FileRow>
          );
        })}
      </FileList>
    </div>
  );
}

function Picker({
  id,
  help,
  onFiles,
  onLinks,
  onClose,
}: {
  id: string;
  help: string | null;
  onFiles(files: File[]): void;
  onLinks(links: string[]): Promise<{ left: string[]; problem: "not_a_link" | "failed" | null }>;
  onClose(): void;
}) {
  const [dragging, setDragging] = useState(false);
  const [text, setText] = useState("");
  const [bad, setBad] = useState(false);
  const [failed, setFailed] = useState(false);
  const [adding, setAdding] = useState(false);
  const files = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const ids = useId();

  // A folder is picked with the browser's own folder chooser; every file in it is added (BLD-C214).
  useEffect(() => {
    folder.current?.setAttribute("webkitdirectory", "");
  }, []);

  const addLinks = async () => {
    if (adding) return;
    const { links, typed, bad: wrong } = splitLinks(text);
    if (wrong) {
      setBad(true);
      return;
    }
    setBad(false);
    setFailed(false);
    setAdding(true);
    const { left, problem } = await onLinks(links);
    setAdding(false);
    setText(typed.filter((_, i) => left.includes(links[i]!)).join(", "));
    setBad(problem === "not_a_link");
    setFailed(problem === "failed");
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer?.files ?? []);
    if (dropped.length) onFiles(dropped);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Escape") return;
    e.stopPropagation();
    onClose();
  };

  const picked = (input: HTMLInputElement) => {
    const chosen = Array.from(input.files ?? []);
    input.value = "";
    if (chosen.length) onFiles(chosen);
  };

  return (
    <div
      id={id}
      className="cpick"
      onKeyDown={onKeyDown}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="cpick-drop">
        <button
          type="button"
          className="cpick-folder"
          aria-label={BOX_FILES_COPY.folder}
          title={BOX_FILES_COPY.folder}
          onClick={() => folder.current?.click()}
        >
          <IconFolder size={26} />
        </button>
        <DropArea
          title={BOX_FILES_COPY.dropTitle}
          help={help ? `${help} ${BOX_FILES_COPY.folderLine}` : BOX_FILES_COPY.folderLine}
          dragging={dragging}
          browse={
            <button type="button" className="tb blue" onClick={() => files.current?.click()}>
              {BOX_FILES_COPY.browse}
            </button>
          }
        />
      </div>
      <div className="cpick-link">
        <span className="cpick-li" aria-hidden="true">
          <IconLink />
        </span>
        <label className="vh" htmlFor={`${ids}-u`}>
          {BOX_FILES_COPY.linkInput}
        </label>
        <input
          id={`${ids}-u`}
          className="fld"
          type="url"
          inputMode="url"
          autoComplete="off"
          placeholder={BOX_FILES_COPY.linkInput}
          aria-describedby={bad ? `${ids}-m ${ids}-h` : `${ids}-h`}
          aria-invalid={bad ? true : undefined}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (bad) setBad(false);
          }}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            void addLinks();
          }}
        />
        <Button variant="line" size="sm" busy={adding} onClick={() => void addLinks()}>
          {BOX_FILES_COPY.addLink}
        </Button>
      </div>
      {bad ? <FieldMsg id={`${ids}-m`}>{CHECK_COPY.proof.notALink}</FieldMsg> : null}
      {failed ? <FieldMsg>{CHECK_COPY.failed}</FieldMsg> : null}
      <p className="cpick-h" id={`${ids}-h`}>
        {BOX_FILES_COPY.linkLine}
      </p>
      <input ref={files} type="file" multiple hidden onChange={(e) => picked(e.target)} />
      <input ref={folder} type="file" multiple hidden onChange={(e) => picked(e.target)} />
    </div>
  );
}
