import type { ReactNode } from "react";

/**
 * C-EMPTY: never a blank area. A short title, one or two lines saying what will show here, and at most one action;
 * centred in a card, left-aligned in a list. Exact words come from each screen's states.
 */
export function Empty({
  title,
  children,
  action,
  align = "left",
  level = 3,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  align?: "left" | "center";
  level?: 2 | 3 | 4;
}) {
  const H = `h${level}` as "h2" | "h3" | "h4";
  return (
    <div className={align === "center" ? "emp center" : "emp"}>
      <H className="emp-t">{title}</H>
      {children ? <p className="emp-b">{children}</p> : null}
      {action ? <div className="emp-a">{action}</div> : null}
    </div>
  );
}
