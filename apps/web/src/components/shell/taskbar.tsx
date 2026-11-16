import Link from "next/link";
import type { ReactNode } from "react";

import { IconSync, IconTick } from "./icons";

export type TaskStep = "tell" | "check" | "send";
export type SaveState = "idle" | "saving" | "saved" | "offline" | "changed";

const STEPS: Array<{ key: TaskStep; label: string }> = [
  { key: "tell", label: "Tell it" },
  { key: "check", label: "Check it" },
  { key: "send", label: "Send it" },
];

/** "1:38 pm", India time. */
export function savedTime(at: Date | string): string {
  const d = typeof at === "string" ? new Date(at) : at;
  return d
    .toLocaleTimeString("en-IN", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: "Asia/Kolkata",
    })
    .replace(/\s?([ap])\.?m\.?/i, (_, x: string) => ` ${x.toLowerCase()}m`);
}

/** C-TASKBAR.save: the words for each save state. */
export function saveWords(state: SaveState, savedAt?: Date | string | null): string {
  switch (state) {
    case "saving":
      return "Saving…";
    case "saved":
      return savedAt ? `Saved at ${savedTime(savedAt)}` : "Saved";
    case "offline":
      return "Unsaved, you’re offline";
    case "changed":
      return "Unsaved changes";
    default:
      return "Saves as you type";
  }
}

/**
 * C-TASKBAR: the sticky bar across the top of a task screen (Tell it, Check it, Edit). The task's title, the three
 * steps, the save status in a polite live region, and "Save and close". Two step looks are drawn (C-TASKBAR.steps,
 * OPEN: the product owner to choose one): labelled bars on Tell it, numbered nodes on Check it. A done step links back.
 * `steps={false}` hides the steps, as Tell it does before the first message (S-04.empty).
 */
export function Taskbar({
  title = "Share a problem",
  step,
  look = step === "tell" ? "bars" : "nodes",
  steps = true,
  stepHrefs = {},
  save,
  savedAt,
  closeHref,
  closeLabel = "Save and close",
  offlineNote,
  extra,
}: {
  title?: string;
  step: TaskStep;
  look?: "bars" | "nodes";
  steps?: boolean;
  /** Where each done step links back to. */
  stepHrefs?: Partial<Record<TaskStep, string>>;
  save: SaveState;
  savedAt?: Date | string | null;
  closeHref: string;
  closeLabel?: string;
  /** The warning note under the bar while offline; its words come from the screen's copy. */
  offlineNote?: string;
  /** Anything a screen adds to the bar's middle (Edit's line, for example). */
  extra?: ReactNode;
}) {
  const at = STEPS.findIndex((s) => s.key === step);
  return (
    <header className="tbar">
      <div className="tbar-in">
        <span className="tbar-t">{title}</span>
        {steps ? (
          <ol
            className={look === "bars" ? "tsteps tsteps-bars" : "tsteps tsteps-nodes"}
            aria-label="Progress"
          >
            {STEPS.map((s, i) => {
              const state = i < at ? "done" : i === at ? "now" : "next";
              const href = state === "done" ? stepHrefs[s.key] : undefined;
              const mark =
                look === "nodes" ? (
                  <span className="tsn" aria-hidden="true">
                    {state === "done" ? <IconTick size={12} /> : i + 1}
                  </span>
                ) : null;
              const words = (
                <>
                  {mark}
                  <span className="tsl">{s.label}</span>
                  {state === "done" ? <span className="vh">, done</span> : null}
                </>
              );
              return (
                <li key={s.key} className={state} aria-current={state === "now" ? "step" : undefined}>
                  {href ? <Link href={href}>{words}</Link> : words}
                </li>
              );
            })}
          </ol>
        ) : null}
        {extra}
        <span className={`saved saved-${save}`} role="status">
          <IconSync />
          {saveWords(save, savedAt)}
        </span>
        <Link href={closeHref} className="btn btn-secondary btn-sm tbar-close">
          {closeLabel}
        </Link>
      </div>
      {save === "offline" && offlineNote ? <p className="tbar-note">{offlineNote}</p> : null}
    </header>
  );
}
