"use client";
/**
 * C-FILE.uploader, the picker the "+" opens (the Home board's `attachments=Picker open`; BLD-D031): "Choose a folder",
 * the drop area with "browse", and the link field with "Add link". One picker for the prompt box (Home, Share a
 * problem, the draft page; lane C's `box-files.tsx`) and the conversation box (S-08; lane F's `attach.tsx`), which drew
 * their own copies before. The screen keeps its own root class for its place (`cpick`, `cv-pick`) and its own logic for
 * what a file or a link does; the picker only takes them in.
 *
 * - The controls are, in order, "Choose a folder", "browse", the link field and "Add link"; both file inputs carry the
 *   `hidden` attribute, so S-08's focus carry across 640px (BLD-F098) finds the same four by index.
 * - A dropped folder adds every file in it through the browser's directory entries; where the browser gives none, the
 *   picker says to use "Choose a folder" (BLD-C224). Every file goes through the screen's `onFiles`. The walk leaves
 *   out the system's own entries, a file whose name or any folder on its path starts with "." (".git/", ".DS_Store"),
 *   by the rule "Choose a folder" uses on both screens (BLD-D040, BLD-C248, BLD-F109).
 * - Escape closes it from anywhere inside; the screen puts the focus back on the "+".
 * - Links are kept as typed and never fetched (BLD-E001): `onLinks` gets them, and either takes them at once (S-08 puts
 *   them in the words) or answers with those it could not add (Home adds them as rows, with "Add link" busy meanwhile).
 */
import { useEffect, useId, useRef, useState, type DragEvent, type KeyboardEvent } from "react";

import { CHECK_COPY } from "@/app/share/[id]/check/copy";
import { splitLinks } from "@/app/share/[id]/check/model";
import { IconFolder, IconLink } from "@/components/compose/icons";
import { Button } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { DropArea } from "@/components/ui/file";

/** The Home board's words for the picker (reference/copy/Home.md, `attachments`). Not to be rewritten. */
export const PICKER_COPY = {
  dropTitle: "Drop files or a folder here, or",
  browse: "browse",
  folder: "Choose a folder",
  folderLine: "Tap the folder to add a whole folder.",
  linkInput: "Or paste a link to a page, file or idea",
  addLink: "Add link",
  linkLine: "SharePoint, Teams and 1% Club links are marked internal. Anything else is marked external.",
  /** To confirm later (HR, DEC-123; BLD-C224): a folder dropped where the browser gives no way to read it. */
  useFolder: "Use Choose a folder to add a folder.",
  /** A dropped folder with only the system's files: the share box's line for the same pick, word for word
   * (BOX_FILES_COPY.onlyDotFiles, BLD-C224, BLD-C248; BLD-D040). */
  onlyDotFiles: "Nothing was added. Files whose names start with a dot are left out.",
} as const;

/** The link field's words, and whether "Add link" found they are not a link. */
export interface LinkDraft {
  text: string;
  bad: boolean;
}

export const NO_LINK: LinkDraft = { text: "", bad: false };

/** What became of the links handed over: those still to add stay in the field, with why. */
export type LinksAnswer = { left: string[]; problem: "not_a_link" | "failed" | null };

/** The link field as the screen keeps it, so a picker drawn again still holds it (BLD-F102); else the picker's own.
 * Both or neither: a field passed without its setter could never change (BLD-D040). */
type LinkField =
  { link: LinkDraft; onLinkDraft(next: LinkDraft): void } | { link?: undefined; onLinkDraft?: undefined };

export function FilePicker({
  id,
  className,
  help,
  autoFocus = true,
  note,
  onNote,
  link,
  onLinkDraft,
  linkHelp,
  onFiles,
  onLinks,
  onClose,
}: {
  /** The "+" points at it (`aria-controls`). */
  id: string;
  /** The screen's own name for its place (`cpick`, `cv-pick`), added to `fpick`. */
  className?: string;
  /** The configured types and limit (C-FILE.uploader/1, BLD-E007); the folder line follows it. */
  help: string | null;
  /** WCAG 2.4.3: the focus goes to "Choose a folder" when it opens (BLD-C224). S-08 moves the focus itself. */
  autoFocus?: boolean;
  /** A line the screen keeps (why nothing was added); without `onNote` the picker keeps its own. */
  note?: string | null;
  onNote?(note: string | null): void;
  /** The line under the link field (Home: internal and external links). */
  linkHelp?: string;
  onFiles(files: File[]): void;
  /** The links, and the field's words as typed. Nothing back: all taken; an answer: what is left, and why. */
  onLinks(links: string[], typed: string): Promise<LinksAnswer> | void;
  onClose(): void;
} & LinkField) {
  const [dragging, setDragging] = useState(false);
  const [ownNote, setOwnNote] = useState<string | null>(null);
  const [ownLink, setOwnLink] = useState<LinkDraft>(NO_LINK);
  const [failed, setFailed] = useState(false);
  const [adding, setAdding] = useState(false);
  const files = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const first = useRef<HTMLButtonElement>(null);
  const ids = useId();
  const shownNote = onNote ? (note ?? null) : ownNote;
  const say = onNote ?? setOwnNote;
  const { text, bad } = link ?? ownLink;
  const setLink = onLinkDraft ?? setOwnLink;

  // A folder is picked with the browser's own folder chooser; every file in it is added (BLD-C214)
  useEffect(() => {
    folder.current?.setAttribute("webkitdirectory", "");
    if (autoFocus) first.current?.focus();
  }, [autoFocus]);

  const addLinks = async () => {
    if (adding) return;
    const { links, typed, bad: wrong } = splitLinks(text);
    if (wrong) {
      setLink({ text, bad: true });
      return;
    }
    setFailed(false);
    const answer = onLinks(links, text.trim());
    if (!answer) {
      setLink(NO_LINK);
      return;
    }
    setLink({ text, bad: false });
    setAdding(true);
    const { left, problem } = await answer;
    setAdding(false);
    setLink({
      text: typed.filter((_, i) => left.includes(links[i]!)).join(", "),
      bad: problem === "not_a_link",
    });
    setFailed(problem === "failed");
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    say(null);
    const dropped = droppedOf(e.dataTransfer);
    if (dropped.some((d) => d.entry?.isDirectory)) {
      // A folder dropped here: its files through the browser's directory entries (BLD-C224)
      void filesOfDrop(dropped).then(
        ({ got, leftOut }) =>
          got.length ? onFiles(got) : say(leftOut ? PICKER_COPY.onlyDotFiles : PICKER_COPY.useFolder),
        () => say(PICKER_COPY.useFolder),
      );
      return;
    }
    // No directory entries: a folder arrives as an empty file with no type, which can never upload
    const real = dropped.flatMap((d) =>
      d.file && !(d.entry === null && looksLikeFolder(d.file)) ? [d.file] : [],
    );
    if (real.length < dropped.length) say(PICKER_COPY.useFolder);
    if (real.length) onFiles(real);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    onClose();
  };

  const picked = (input: HTMLInputElement) => {
    const chosen = Array.from(input.files ?? []);
    input.value = "";
    if (chosen.length) onFiles(chosen);
  };

  const described =
    [bad ? `${ids}-m` : "", linkHelp ? `${ids}-h` : ""].filter(Boolean).join(" ") || undefined;

  return (
    <div
      id={id}
      className={className ? `fpick ${className}` : "fpick"}
      onKeyDown={onKeyDown}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="fpick-drop">
        <button
          ref={first}
          type="button"
          className="fpick-folder"
          aria-label={PICKER_COPY.folder}
          title={PICKER_COPY.folder}
          onClick={() => folder.current?.click()}
        >
          <IconFolder size={26} />
        </button>
        <DropArea
          title={PICKER_COPY.dropTitle}
          help={help ? `${help} ${PICKER_COPY.folderLine}` : PICKER_COPY.folderLine}
          dragging={dragging}
          browse={
            <button type="button" className="tb blue" onClick={() => files.current?.click()}>
              {PICKER_COPY.browse}
            </button>
          }
        />
      </div>
      <div className="fpick-link">
        <span className="fpick-li" aria-hidden="true">
          <IconLink />
        </span>
        <label className="vh" htmlFor={`${ids}-u`}>
          {PICKER_COPY.linkInput}
        </label>
        <input
          id={`${ids}-u`}
          className="fld"
          type="url"
          inputMode="url"
          autoComplete="off"
          placeholder={PICKER_COPY.linkInput}
          aria-describedby={described}
          aria-invalid={bad ? true : undefined}
          value={text}
          onChange={(e) => setLink({ text: e.target.value, bad: false })}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault(); // never the box's own send
            void addLinks();
          }}
        />
        <Button variant="line" size="sm" busy={adding} onClick={() => void addLinks()}>
          {PICKER_COPY.addLink}
        </Button>
      </div>
      {shownNote ? <FieldMsg>{shownNote}</FieldMsg> : null}
      {bad ? <FieldMsg id={`${ids}-m`}>{CHECK_COPY.proof.notALink}</FieldMsg> : null}
      {failed ? <FieldMsg>{CHECK_COPY.failed}</FieldMsg> : null}
      {linkHelp ? (
        <p className="fpick-h" id={`${ids}-h`}>
          {linkHelp}
        </p>
      ) : null}
      <input ref={files} type="file" multiple hidden onChange={(e) => picked(e.target)} />
      <input ref={folder} type="file" multiple hidden onChange={(e) => picked(e.target)} />
    </div>
  );
}

type Entry = {
  /** The entry's own name: a dropped File carries no path, so only the walk sees ".git/" (BLD-D040). */
  name?: string;
  isFile: boolean;
  isDirectory: boolean;
  file?(ok: (f: File) => void, err: (e: unknown) => void): void;
  createReader?(): { readEntries(ok: (es: Entry[]) => void, err: (e: unknown) => void): void };
};
type Dropped = { file: File | null; entry: Entry | null };

/** Each dropped file, with its entry: read during the drop event, which the browser clears once it returns. */
function droppedOf(data: DataTransfer | null): Dropped[] {
  const items = Array.from(data?.items ?? []).filter((i) => i.kind === "file");
  if (!items.length) return Array.from(data?.files ?? []).map((file) => ({ file, entry: null }));
  return items.map((i) => {
    const get = (i as { webkitGetAsEntry?: () => Entry | null }).webkitGetAsEntry;
    return { file: i.getAsFile(), entry: typeof get === "function" ? get.call(i) : null };
  });
}

/** The files of a drop with a folder in it: every file in every folder, one level of nesting at a time, and whether
 * the walk left any out. A file dropped on its own keeps its name as its path, so the screen's own check sees it. */
async function filesOfDrop(dropped: Dropped[]): Promise<{ got: File[]; leftOut: boolean }> {
  const got: File[] = [];
  const walk = { leftOut: false };
  for (const d of dropped) {
    if (d.entry?.isDirectory) got.push(...(await filesOfEntry(d.entry, 0, walk)));
    else if (d.file) got.push(d.file);
  }
  return { got, leftOut: walk.leftOut };
}

const FOLDER_DEPTH = 8;

/** A folder's own entries for the system (".git/", ".svn/", ".vscode/", ".DS_Store"): the name starts with ".". The
 * walk never enters such a folder, so a file is left out when its name or any folder on its path starts with ".",
 * as in "Choose a folder" on both screens (BLD-C248, BLD-F109; BLD-D040). */
const isSystemEntry = (entry: Entry) => entry.name?.startsWith(".") ?? false;

async function filesOfEntry(entry: Entry, depth: number, walk: { leftOut: boolean }): Promise<File[]> {
  if (isSystemEntry(entry)) {
    walk.leftOut = true;
    return [];
  }
  if (entry.isFile && entry.file) return [await new Promise<File>((ok, err) => entry.file!(ok, err))];
  if (!entry.isDirectory || !entry.createReader || depth > FOLDER_DEPTH) return [];
  const reader = entry.createReader();
  const out: File[] = [];
  for (;;) {
    const batch = await new Promise<Entry[]>((ok, err) => reader.readEntries(ok, err));
    if (!batch.length) return out;
    for (const e of batch) out.push(...(await filesOfEntry(e, depth + 1, walk)));
  }
}

/** A folder dropped where the browser gives no entries: an empty file with no type. */
function looksLikeFolder(f: File): boolean {
  return f.size === 0 && f.type === "";
}
