import type { ReactNode } from "react";

import { IconTick } from "@/components/shell/icons";

/**
 * C-FILE, the row and the drop area (UI only; the upload, quarantine, scan and polling stay in the screen's own
 * logic, e.g. share/[id]/attachments.tsx). A type badge, the name, the size, a status, one or two actions, and a
 * message under the row when something needs the person. Links are never fetched (BLD-E001), so there is no
 * "couldn't open this link" state.
 */
export type FileStatus = "uploading" | "checking" | "checked" | "hidden" | "failed" | "found" | "too-big";

const BADGE: Record<string, string> = {
  pdf: "PDF",
  png: "PNG",
  jpg: "JPG",
  jpeg: "JPG",
  docx: "DOC",
  doc: "DOC",
  xlsx: "XLSX",
  xls: "XLSX",
  csv: "CSV",
  pptx: "PPT",
  ppt: "PPT",
  md: "MD",
  html: "HTML",
  zip: "ZIP",
  link: "Link",
  folder: "Folder",
};

export function fileKind(name: string): string {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  return Object.hasOwn(BADGE, ext) ? ext : "file";
}

/** The badge's words for a kind from `fileKind`, or "link" / "folder"; anything else reads "File" (C-FILE.row). */
export function fileBadge(kind: string): string {
  return (Object.hasOwn(BADGE, kind) ? BADGE[kind] : undefined) ?? "File";
}

export function FileRow({
  name,
  kind = fileKind(name),
  size,
  status,
  statusText,
  message,
  progress,
  children,
}: {
  name: string;
  kind?: string;
  /** "2.4 MB", or for a folder "6 files, 3.1 MB". */
  size?: string;
  status: FileStatus;
  /** What the status says ("Checked", "Folio hidden", "Checking for personal details"). */
  statusText: string;
  /** The error or warning under the row (C-FIELD-MSG look). */
  message?: { kind: "error" | "warn"; text: ReactNode };
  /** 0 to 1 while uploading. */
  progress?: number;
  /** The row's actions: View, Remove, Try again, Hide it for me. */
  children?: ReactNode;
}) {
  const ok = status === "checked" || status === "hidden";
  return (
    <li className={`frow frow-${status}`}>
      <div className="frow-in">
        <span className={`fbadge fb-${kind}`} aria-hidden="true">
          {fileBadge(kind)}
        </span>
        <span className="frow-b">
          <span className="frow-n">{name}</span>
          <span className="frow-s">
            {size ? <span>{size}</span> : null}
            <span className={ok ? "frow-st ok" : "frow-st"}>
              {status === "checking" ? <span className="spin" aria-hidden="true" /> : null}
              {ok ? <IconTick size={14} /> : null}
              {statusText}
            </span>
          </span>
          {status === "uploading" && progress !== undefined ? (
            <span className="frow-p" aria-hidden="true">
              <i style={{ width: `${Math.round(Math.min(1, Math.max(0, progress)) * 100)}%` }} />
            </span>
          ) : null}
        </span>
        {children ? <span className="frow-a">{children}</span> : null}
      </div>
      {message ? (
        <p className={message.kind === "warn" ? "fmsg warn" : "fmsg"} role="alert">
          <span className="fmsg-ic" aria-hidden="true" />
          <span>{message.text}</span>
        </p>
      ) : null}
    </li>
  );
}

/** The list of file rows; announces changes politely. */
export function FileList({ label, children }: { label: string; children: ReactNode }) {
  return (
    <ul className="flist" aria-label={label} aria-live="polite" role="list">
      {children}
    </ul>
  );
}

/**
 * The drop area (C-FILE.uploader). Drag and drop always has a browse alternative: `browse` is the screen's own
 * file input button. The help line is rendered from the configured types and limit (BLD-E007), never hard-coded.
 */
export function DropArea({
  title,
  help,
  browse,
  dragging,
}: {
  /** "Drop files here, or" — the browse control completes the sentence. */
  title: ReactNode;
  help: ReactNode;
  browse: ReactNode;
  dragging?: boolean;
}) {
  return (
    <div className={dragging ? "fdrop on" : "fdrop"}>
      <p className="fdrop-t">
        {title} {browse}
      </p>
      <p className="fdrop-h">{help}</p>
    </div>
  );
}
