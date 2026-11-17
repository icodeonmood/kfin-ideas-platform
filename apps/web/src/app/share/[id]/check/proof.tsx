"use client";

/**
 * Part 4, "Anything that shows it?": lane D's C-FILE rows and drop area (components/ui/file.tsx), wired to A-API.files.
 * "Attach files" opens the drop area, whose "browse" opens the file picker (C-FILE.uploader/5); a file can also be
 * dropped or pasted. The link field takes one link or several with commas; links are kept as typed and never
 * fetched (BLD-E001), so a link row says only whether it is internal or external. Each file is checked for personal
 * details before anyone but the sharer can open it (L-HIDE.files); one failed file never blocks the others
 * (C-FILE.uploader/4). The help line is the configured one when GET /config carries uploads (BLD-E007).
 */
import { useId, useRef, useState, type ClipboardEvent, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import { DropArea, FileList, FileRow } from "@/components/ui/file";

import { CHECK_COPY, PARTS } from "./copy";
import { rowView, splitLinks, type ProofItem } from "./model";

const C = CHECK_COPY.proof;

export function ProofBody({
  items,
  limitMb,
  help,
  accept,
  onFiles,
  onLinks,
  onRetry,
  onHide,
  onRemove,
  showHelps,
  edit,
}: {
  items: ProofItem[];
  limitMb: number;
  help: string;
  accept?: string;
  onFiles(files: File[]): void;
  /** "ok", or what went wrong: a piece that is not a link, or the call failing. */
  onLinks(links: string[]): Promise<"ok" | "not_a_link" | "failed">;
  onRetry(key: string): void;
  onHide(key: string): void;
  onRemove(key: string): void;
  showHelps: boolean;
  /**
   * The edit page's look (S-06B; Edit.md, PhoneEdit.md): the drop area always open above the link field, or on a
   * phone one button that opens the file picker, and the link field in the edit boards' words. Check it leaves it
   * out and keeps "Attach files".
   */
  edit?: {
    /** "Link to a report, dashboard or ticket" (read out, not shown: the field says it). */
    links: string;
    /** "Or paste a link to a report, dashboard or ticket"; on a phone "Or paste a link". */
    linkInput: string;
    /** "Add link"; on a phone "Add". */
    addLink: string;
    /** Phone: "Add a photo or file" with its line, in place of the drop area. */
    pick?: { label: string; line: string };
  };
}) {
  const [open, setOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [text, setText] = useState("");
  const [bad, setBad] = useState(false);
  const [failed, setFailed] = useState(false);
  const [adding, setAdding] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const ids = useId();

  const addLinks = async () => {
    const { links, bad: wrong } = splitLinks(text);
    if (wrong) {
      setBad(true);
      return;
    }
    setBad(false);
    setFailed(false);
    setAdding(true);
    const result = await onLinks(links);
    setAdding(false);
    if (result === "ok") setText("");
    else if (result === "not_a_link") setBad(true);
    else setFailed(true);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length) onFiles(files);
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const files = Array.from(e.clipboardData?.files ?? []);
    if (files.length) {
      e.preventDefault();
      onFiles(files);
    }
  };

  const browse = (
    <button type="button" className="tb blue" onClick={() => input.current?.click()}>
      {C.browse}
    </button>
  );
  // The edit page: a phone gets one button that opens the picker; a desk the drop area, always open.
  const picker = edit?.pick ? (
    <button type="button" className="ck-pick tile" onClick={() => input.current?.click()}>
      <span className="ck-pick-t">{edit.pick.label}</span>
      <span className="ck-pick-l meta">{edit.pick.line}</span>
    </button>
  ) : (
    <DropArea title={C.dropTitle} help={help} dragging={dragging} browse={browse} />
  );

  return (
    <div
      className={edit ? "ck-proof ck-proof-edit" : "ck-proof"}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      {edit ? picker : null}
      {edit ? (
        <span className="vh" id={`${ids}-l`}>
          {edit.links}
        </span>
      ) : (
        <p className="lbl" id={`${ids}-l`}>
          {C.links}
        </p>
      )}
      <span className="vh" id={`${ids}-p`}>
        {edit ? edit.linkInput : C.linkInput}
      </span>
      <div className="ck-linkrow">
        <input
          className="fld"
          type={edit ? "url" : "text"}
          inputMode="url"
          autoComplete="off"
          placeholder={edit ? edit.linkInput : C.linkInput}
          aria-labelledby={edit ? `${ids}-p` : `${ids}-l ${ids}-p`}
          aria-describedby={bad ? `${ids}-m` : edit ? `${ids}-l` : undefined}
          aria-invalid={bad ? true : undefined}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (bad) setBad(false);
          }}
          onPaste={onPaste}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void addLinks();
            }
          }}
        />
        {edit ? null : (
          <Button
            variant="line"
            size="sm"
            aria-expanded={open}
            aria-haspopup="dialog"
            aria-controls={open ? `${ids}-drop` : undefined}
            onClick={() => setOpen((v) => !v)}
          >
            {C.attach}
          </Button>
        )}
        <Button variant="line" size="sm" busy={adding} onClick={() => void addLinks()}>
          {edit ? edit.addLink : C.addLink}
        </Button>
      </div>
      {bad ? <FieldMsg id={`${ids}-m`}>{C.notALink}</FieldMsg> : null}
      {failed ? <FieldMsg>{CHECK_COPY.failed}</FieldMsg> : null}
      <input
        ref={input}
        type="file"
        multiple
        hidden
        accept={accept}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          if (files.length) onFiles(files);
        }}
      />
      {!edit && (open || dragging) ? (
        <div id={`${ids}-drop`}>
          <DropArea title={C.dropTitle} help={help} dragging={dragging} browse={browse} />
        </div>
      ) : null}
      {items.length ? (
        <FileList label={PARTS[3].label}>
          {items.map((p) => {
            const v = rowView(p, limitMb);
            return (
              <FileRow
                key={p.key}
                name={p.item?.name ?? p.name}
                kind={v.kind}
                size={v.size}
                status={v.status}
                statusText={v.statusText}
                message={v.message}
              >
                {v.actions.includes("view") && p.item?.view_url ? (
                  <a
                    className="tb blue"
                    href={p.item.view_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={C.viewOf(p.item.name)}
                  >
                    {C.view}
                  </a>
                ) : null}
                {v.actions.includes("retry") ? (
                  <Button variant="text-blue" onClick={() => onRetry(p.key)}>
                    {CHECK_COPY.retry}
                  </Button>
                ) : null}
                {v.actions.includes("hide") ? (
                  <Button variant="text-blue" onClick={() => onHide(p.key)}>
                    {C.hideForMe}
                  </Button>
                ) : null}
                <Button
                  variant="text"
                  aria-label={C.removeOf(p.item?.name ?? p.name)}
                  onClick={() => onRemove(p.key)}
                >
                  {C.remove}
                </Button>
              </FileRow>
            );
          })}
        </FileList>
      ) : showHelps ? (
        <div className="ck-helps">
          <p className="lbl">{C.helpsTitle}</p>
          <ul>
            {C.helps.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
