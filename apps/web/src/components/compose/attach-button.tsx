"use client";
/**
 * The "+" that opens the attach picker, first in every prompt box's tool row (DEC-124; C-PROMPT.attach,
 * C-PROMPT.anatomy/2, in place of the board's paperclip). Lane C's stand-in for lane D's shared `AttachButton`
 * (`@/components/ui/attach-button`, BLD-D019), which was not on main when this was built (BLD-C213): same props, same
 * class (`.attach-btn`, styled in app/share/compose.css), so lane D folds it into the shared copy at QA. Its name and
 * tooltip are fixed: "Add files, a folder or a link" (Home.md, `attachments=Picker open`). Icon only, so the name is
 * `aria-label`; the target is 44 × 44 CSS px (at least 24 × 24, WCAG 2.5.8) with a visible focus ring.
 */
import type { MouseEvent } from "react";

import { IconPlus } from "@/components/compose/icons";

export const ATTACH_LABEL = "Add files, a folder or a link";

export function AttachButton({
  onClick,
  disabled,
  className,
  "aria-expanded": expanded,
  "aria-controls": controls,
}: {
  onClick?(e: MouseEvent<HTMLButtonElement>): void;
  disabled?: boolean;
  className?: string;
  "aria-expanded"?: boolean;
  "aria-controls"?: string;
}) {
  return (
    <button
      type="button"
      className={`attach-btn${className ? ` ${className}` : ""}`}
      aria-label={ATTACH_LABEL}
      title={ATTACH_LABEL}
      aria-expanded={expanded}
      aria-controls={controls}
      aria-disabled={disabled ? true : undefined}
      onClick={(e) => {
        if (disabled) return;
        onClick?.(e);
      }}
    >
      <IconPlus />
    </button>
  );
}
