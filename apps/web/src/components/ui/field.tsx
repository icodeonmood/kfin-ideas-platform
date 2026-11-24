"use client";

import { useId, type ReactNode } from "react";

/**
 * C-FIELD-MSG: what went wrong, or what needs attention, said right under the field or group it is about. A tinted
 * note with a round "!" icon, announced (role="alert"), there until the cause is fixed. Never a toast.
 */
export function FieldMsg({
  id,
  kind = "error",
  children,
}: {
  id?: string;
  kind?: "error" | "warn";
  children: ReactNode;
}) {
  return (
    <p id={id} className={kind === "warn" ? "fmsg field-msg warn" : "fmsg field-msg"} role="alert">
      <span className="fmsg-ic" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}

export type FieldControlProps = {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  className: string;
};

/**
 * C-FIELD: a label above, the field, an optional help line, and its message. The control is rendered by the caller
 * with the props this hands it, so every input, text area or select is wired the same way: the label points at it,
 * the help and the message describe it, and an error marks it invalid (F-A11Y.rules/5–6). With `tools`, the field's
 * own icon buttons sit inside its frame at the trailing end (BLD-D029).
 */
export function Field({
  label,
  optional,
  help,
  error,
  warning,
  multiline,
  tools,
  children,
}: {
  label: ReactNode;
  /** Shows "Optional" after the label in the muted weight. */
  optional?: boolean;
  /** The help line, or a live counter ("12 of at least 30 characters"). */
  help?: ReactNode;
  error?: ReactNode;
  warning?: ReactNode;
  multiline?: boolean;
  /**
   * C-PROMPT.anatomy/2 (BLD-D029): icon buttons at the field's trailing end, inside its frame, as the Answer board draws
   * the "+" and the mic in its field (S-R3). The frame then takes the field's border, fill, focus and invalid states and
   * the control inside draws none. Each tool is a button with its own name, after the control in the reading order.
   */
  tools?: ReactNode;
  children: (control: FieldControlProps) => ReactNode;
}) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const msgId = error || warning ? `${id}-msg` : undefined;
  const describedBy = [helpId, msgId].filter(Boolean).join(" ") || undefined;
  const control = children({
    id,
    "aria-describedby": describedBy,
    "aria-invalid": error ? true : undefined,
    className: multiline ? "fld textarea" : "fld",
  });
  return (
    <div className="fld-wrap">
      <label className="lbl" htmlFor={id}>
        {label}
        {optional ? <span className="opt"> Optional</span> : null}
      </label>
      {tools ? (
        // Firefox 111 has no :has(), so the frame is told the field's state rather than reading it from the control
        <div
          className={["fld-frame", multiline ? "multi" : "", error ? "invalid" : ""]
            .filter(Boolean)
            .join(" ")}
        >
          {control}
          <span className="fld-tools">{tools}</span>
        </div>
      ) : (
        control
      )}
      {help ? (
        <p id={helpId} className="help">
          {help}
        </p>
      ) : null}
      {error ? (
        <FieldMsg id={msgId}>{error}</FieldMsg>
      ) : warning ? (
        <FieldMsg id={msgId} kind="warn">
          {warning}
        </FieldMsg>
      ) : null}
    </div>
  );
}
