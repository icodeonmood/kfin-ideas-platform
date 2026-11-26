"use client";

import { forwardRef, type MouseEvent } from "react";

/** The board's words for the button and its tooltip (reference/copy/Home.md; DEC-124). Not to be rewritten. */
export const ATTACH_NAME = "Add files, a folder or a link";

export type AttachButtonProps = {
  /** Opens the picker (C-FILE.uploader); the screen that mounts the button wires it. */
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  /** Whether the picker it opens is open. */
  "aria-expanded"?: boolean;
  /** The picker's id. */
  "aria-controls"?: string;
  /** Shown as aria-disabled; the button stays focusable and a click does nothing (C-BUTTON.states/4). */
  disabled?: boolean;
  className?: string;
  /** The button's name (aria-label); `ATTACH_NAME` unless the box's board names it otherwise. S-R3 passes the Answer
   * board's "Attach files to this answer", because its "+" opens files only (BLD-B275, approved by lane D). */
  label?: string;
  /** The tooltip (title); `ATTACH_NAME` unless the board draws another ("Attach files" on S-R3). */
  tooltip?: string;
};

/**
 * C-PROMPT.anatomy/2, DEC-124 (BLD-D019): the subtle "+" attach icon button, first in a prompt box's tool row
 * (attach, then the mic, then send), on Home, Share a problem, the draft page and the conversation's box. A 44px round
 * target in the tool row's look: transparent at rest in `--ink2`, the row's hover fill, ink when its picker is open,
 * pressed to 0.94, the 2px blue focus ring. The "+" is drawn at F-ICONS stroke 2 for actions and takes the text's
 * colour; not the board's paperclip. Its name and tooltip are exactly "Add files, a folder or a link".
 *
 * Only the button: the screen wires the picker and the menu through `onClick`, `aria-expanded` and `aria-controls`.
 */
export const AttachButton = forwardRef<HTMLButtonElement, AttachButtonProps>(function AttachButton(
  {
    onClick,
    "aria-expanded": expanded,
    "aria-controls": controls,
    disabled,
    className,
    label = ATTACH_NAME,
    tooltip = ATTACH_NAME,
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      className={className ? `attach-btn ${className}` : "attach-btn"}
      aria-label={label}
      title={tooltip}
      aria-expanded={expanded}
      aria-controls={controls}
      aria-disabled={disabled ? true : undefined}
      onClick={(e) => {
        if (disabled) {
          e.preventDefault();
          return;
        }
        onClick?.(e);
      }}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        <path d="M12 5v14M5 12h14" />
      </svg>
    </button>
  );
});
