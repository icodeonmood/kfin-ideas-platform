import { IconTick } from "@/components/shell/icons";

/**
 * C-TRACK: the five stages as nodes on a line, horizontal on desktop and vertical on a phone or a narrow card. An
 * ordered list; each stage's words carry its state for a screen reader. Not interactive. The line draws and the nodes
 * pop on arrival (motion.css); with reduced motion it simply appears.
 */
export type StageKey = "shared" | "checked" | "reviewed" | "built" | "shipped";
export type StageState = "done" | "now" | "next" | "off";

export const STAGES: Array<{ key: StageKey; name: string }> = [
  { key: "shared", name: "Shared" },
  { key: "checked", name: "Checked and matched" },
  { key: "reviewed", name: "Reviewed" },
  { key: "built", name: "Built" },
  { key: "shipped", name: "Shipped" },
];

const SUFFIX: Record<StageState, string> = {
  done: "done",
  now: "now",
  next: "to come",
  off: "not going ahead",
};

export type TrackStage = { state: StageState; line?: string };

export function Track({
  stages,
  layout = "auto",
  label = "Where it is",
}: {
  /** One entry per stage, in order: its state and its detail line (C-TRACK.detail). */
  stages: Record<StageKey, TrackStage>;
  /** auto: horizontal from 641 px, vertical below; or force one. */
  layout?: "auto" | "horizontal" | "vertical";
  label?: string;
}) {
  const doneCount = STAGES.filter((s) => stages[s.key].state === "done").length;
  const fill = Math.max(0, Math.min(4, doneCount - (stages.shipped.state === "done" ? 1 : 0)));
  const items = STAGES.map((s) => {
    const st = stages[s.key];
    return (
      <li key={s.key} className={st.state}>
        <span className="nd" aria-hidden="true">
          {st.state === "done" ? <IconTick size={12} /> : null}
        </span>
        <p className="sn">
          {s.name}
          <span className="vh">, {SUFFIX[st.state]}</span>
        </p>
        {st.line ? <p className="sw">{st.line}</p> : null}
        {st.state === "now" ? (
          <span className="nowtag" aria-hidden="true">
            Now
          </span>
        ) : null}
      </li>
    );
  });
  const horizontal = (
    <ol
      className={layout === "auto" ? "trk auto" : "trk"}
      aria-label={label}
      style={{ ["--fill-i" as string]: fill }}
    >
      {items}
    </ol>
  );
  const vertical = (
    <ol className={layout === "auto" ? "vtrk auto" : "vtrk"} aria-label={label}>
      {items}
    </ol>
  );
  if (layout === "horizontal") return horizontal;
  if (layout === "vertical") return vertical;
  return (
    <>
      {horizontal}
      {vertical}
    </>
  );
}
