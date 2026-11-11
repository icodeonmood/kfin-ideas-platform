/**
 * The design system's status messages (DEC-099, the Status component): each state has its own shape, glyph and
 * role, so "something broke", "check this first" and "coming soon" never look alike. Words always carry the
 * meaning; the glyph only repeats it.
 *
 * - error: role="alert" by default (pass role={undefined} where a parent region already announces it)
 * - check: the amber "check first" notice
 * - soon: "Coming soon" (dashed)
 */
import type { ReactNode } from "react";

type Kind = "error" | "check" | "soon";

const GLYPH: Record<Kind, ReactNode> = {
  error: <path d="M10 5v6.5M10 14.6v.1" />,
  check: <path d="M10 5v6.5M10 14.6v.1" />,
  soon: <circle cx="10" cy="10" r="6.5" strokeDasharray="2.4 2.4" />,
};

export function StatusGlyph({ kind }: { kind: Kind }) {
  return (
    <span className="status-glyph" aria-hidden="true">
      <svg className="glyph" viewBox="0 0 20 20" focusable="false">
        {GLYPH[kind]}
      </svg>
    </span>
  );
}

export function Status({
  kind,
  title,
  children,
  role,
  id,
  className = "",
  tabIndex,
}: {
  kind: Kind;
  title: ReactNode;
  children?: ReactNode;
  role?: "alert" | "status" | null;
  id?: string;
  className?: string;
  tabIndex?: number;
}) {
  const resolvedRole = role === null ? undefined : (role ?? (kind === "error" ? "alert" : undefined));
  return (
    <div
      className={`status status-${kind} ${className}`.trim()}
      role={resolvedRole}
      id={id}
      tabIndex={tabIndex}
    >
      <StatusGlyph kind={kind} />
      <p className="status-title">{title}</p>
      {children ? <div className="status-body">{children}</div> : null}
    </div>
  );
}
