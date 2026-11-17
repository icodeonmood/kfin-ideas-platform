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
 * the help and the message describe it, and an error marks it invalid (F-A11Y.rules/5–6).
 */
export function Field({
  label,
  optional,
  help,
  error,
  warning,
  multiline,
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
  children: (control: FieldControlProps) => ReactNode;
}) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const msgId = error || warning ? `${id}-msg` : undefined;
  const describedBy = [helpId, msgId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="fld-wrap">
      <label className="lbl" htmlFor={id}>
        {label}
        {optional ? <span className="opt"> Optional</span> : null}
      </label>
      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
        className: multiline ? "fld textarea" : "fld",
      })}
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
