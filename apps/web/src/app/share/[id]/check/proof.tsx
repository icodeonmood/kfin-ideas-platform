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

/** What adding links did: the ones that did not go in (kept in the box), and why. */
export interface LinkResult {
  left: string[];
  problem: "not_a_link" | "failed" | null;
}

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
  canHide,
}: {
  items: ProofItem[];
  limitMb: number;
  help: string;
  accept?: string;
  onFiles(files: File[]): void;
  /** Adds the links one by one and says which did not go in, and why. */
  onLinks(links: string[]): Promise<LinkResult>;
  onRetry(key: string): void;
  onHide(key: string): void;
  onRemove(key: string): void;
  showHelps: boolean;
  /** "Hide it for me" is offered only while `files.blackout` is on (DEC-107, BLD-C064); it starts off. */
  canHide: boolean;
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
    // What went in leaves the box; what did not stays, as typed, to try again.
    setText(typed.filter((_, i) => left.includes(links[i]!)).join(", "));
    setBad(problem === "not_a_link");
    setFailed(problem === "failed");
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

  return (
    <div
      className="ck-proof"
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <p className="lbl" id={`${ids}-l`}>
        {C.links}
      </p>
      <span className="vh" id={`${ids}-p`}>
        {C.linkInput}
      </span>
      <div className="ck-linkrow">
        <input
          className="fld"
          type="text"
          inputMode="url"
          autoComplete="off"
          placeholder={C.linkInput}
          aria-labelledby={`${ids}-l ${ids}-p`}
          aria-invalid={bad ? true : undefined}
          aria-describedby={bad ? `${ids}-m` : undefined}
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
        <Button variant="line" size="sm" busy={adding} onClick={() => void addLinks()}>
          {C.addLink}
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
      {open || dragging ? (
        <div id={`${ids}-drop`}>
          <DropArea
            title={C.dropTitle}
            help={help}
            dragging={dragging}
            browse={
              <button type="button" className="tb blue" onClick={() => input.current?.click()}>
                {C.browse}
              </button>
            }
          />
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
                {v.actions.includes("hide") && canHide ? (
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
