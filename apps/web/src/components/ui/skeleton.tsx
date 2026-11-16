import type { CSSProperties, ReactNode } from "react";

/**
 * C-SKELETON: a loading part shows bars at the size its content will take; lists show three rows. The region is
 * aria-busy with a polite line that says what is loading. No full-screen loaders, ever (C-SKELETON/5).
 */
export function Skeleton({
  width = "100%",
  height = 14,
  tint,
  style,
}: {
  width?: number | string;
  height?: number;
  tint?: boolean;
  style?: CSSProperties;
}) {
  return <span className={tint ? "sk tint" : "sk"} aria-hidden="true" style={{ width, height, ...style }} />;
}

export function Loading({ what, children }: { what: string; children: ReactNode }) {
  return (
    <div aria-busy="true">
      <p className="vh" role="status">
        {what}
      </p>
      {children}
    </div>
  );
}

/** Three skeleton rows for a list. */
export function SkeletonRows({ what, rows = 3 }: { what: string; rows?: number }) {
  return (
    <Loading what={what}>
      <ul className="sk-rows" role="list">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i} className="sk-row">
            <Skeleton width={`${62 - i * 9}%`} height={16} />
            <Skeleton width="38%" height={12} />
          </li>
        ))}
      </ul>
    </Loading>
  );
}

/** C-SKELETON/4: the 12px spinner, for buttons and inline status only. */
export function Spinner() {
  return <span className="spin" aria-hidden="true" />;
}
