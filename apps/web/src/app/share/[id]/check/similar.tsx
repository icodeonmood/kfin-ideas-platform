"use client";

/**
 * C-SIMGRID.grid on Check it, part 3: yours first ("Yours, not sent yet", no actions), then the similar ideas,
 * closest first, three across (two at narrower widths, one on a phone), up to eight more with "Show more" beyond.
 * Each tile (C-SIMGRID.tile): status pill, title, "IDEA-…, area, city", the match line, crew faces and "N colleagues
 * on it", then "Preview" and "Team up", or "Waiting for Ravi" with "Withdraw", or "On the crew".
 * "Preview" opens C-PREVIEW (sharer view); "Team up" opens lane F's sheet (C-SHEET-TEAMUP) with the draft, so the
 * person can ask the lead to merge theirs in or keep it separate. After "Keep mine separate" the grid folds to a
 * note with "Show them again" (C-SIMGRID.grid/4). Match cards show only the masked short summary and the reason
 * (non-negotiable 7): this grid reads nothing else about another person's idea.
 */
import { useState } from "react";

import { IdeaPreviewDialog } from "@/components/preview/idea-preview";
import { CrewFaces } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { StatusPill, type IdeaStatus } from "@/components/ui/pill";
import type { SimilarMatch } from "@/lib/contracts";

import { CHECK_COPY } from "./copy";
import type { MergeView, SimilarLoad, TileAction } from "./model";
import { tileAction } from "./model";
// Swaps to "@/components/teamup/teamup-sheet" when lane F's team-up is on main (the shim goes then).
import { useTeamUpSheet } from "./teamup-shim";

const C = CHECK_COPY.similar;
const SHOWN = 8;

export function SimilarGrid({
  draftId,
  draftTitle,
  draftSummary,
  load,
  merge,
  keptSeparate,
  onShowAgain,
  onChanged,
  onWithdraw,
}: {
  draftId: string;
  draftTitle: string;
  draftSummary: string;
  load: SimilarLoad;
  merge: MergeView | null;
  keptSeparate: boolean;
  onShowAgain(): void;
  /** After a request is sent or withdrawn in the sheet: the part reloads the matches and the merge request. */
  onChanged(): void;
  onWithdraw(action: Extract<TileAction, { kind: "waiting" }>): Promise<void>;
}) {
  const [more, setMore] = useState(false);
  const [previewing, setPreviewing] = useState<SimilarMatch | null>(null);
  const teamUp = useTeamUpSheet({ onSent: onChanged, onWithdrawn: onChanged, draftId, draftTitle });

  if (keptSeparate && load.state === "ok" && load.matches.length) {
    return (
      <div className="ck-kept tile">
        <p>{C.kept}</p>
        <Button variant="text-blue" onClick={onShowAgain}>
          {C.showAgain}
        </Button>
      </div>
    );
  }

  const matches = load.state === "ok" ? load.matches : [];
  const shown = more ? matches : matches.slice(0, SHOWN);
  const previewAction = previewing ? tileAction(previewing, merge) : null;

  return (
    <div className="ck-sim">
      <ul className="simgrid" aria-label={C.grid}>
        <li className="sgt yours">
          <div className="sgt-top">
            <span className="ck-yours">{C.yours}</span>
          </div>
          <p className="sgt-t">{draftTitle}</p>
          {draftSummary ? <p className="sgt-s">{draftSummary}</p> : null}
        </li>
        {shown.map((m) => (
          <Tile
            key={m.idea.id}
            match={m}
            action={tileAction(m, merge)}
            onPreview={() => setPreviewing(m)}
            onTeamUp={() => teamUp.open(m.idea.id)}
            onWithdraw={onWithdraw}
          />
        ))}
      </ul>
      {matches.length > SHOWN && !more ? (
        <Button variant="text-blue" className="ck-more" onClick={() => setMore(true)}>
          {C.showMore}
        </Button>
      ) : null}
      {matches.length ? <p className="meta keepn">{C.carryOn}</p> : null}
      <IdeaPreviewDialog
        ideaId={previewing?.idea.id ?? ""}
        view="sharer"
        open={previewing !== null}
        preview={previewing?.idea}
        matchReason={previewing?.reason}
        yours="draft"
        onClose={() => setPreviewing(null)}
        onPrimary={(id) => teamUp.open(id)}
        primaryDone={
          previewAction?.kind === "waiting"
            ? previewAction.label
            : previewAction?.kind === "on-crew"
              ? C.onCrew
              : undefined
        }
      />
      {teamUp.sheet}
    </div>
  );
}

function Tile({
  match,
  action,
  onPreview,
  onTeamUp,
  onWithdraw,
}: {
  match: SimilarMatch;
  action: TileAction;
  onPreview(): void;
  onTeamUp(): void;
  onWithdraw(action: Extract<TileAction, { kind: "waiting" }>): Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const idea = match.idea;
  const meta = [idea.id, idea.area, idea.city].filter(Boolean).join(", ");
  return (
    <li className="sgt">
      <div className="sgt-top">
        <StatusPill status={idea.status as IdeaStatus} />
      </div>
      <h3 className="sgt-t">{idea.title}</h3>
      <p className="meta">{meta}</p>
      {match.reason ? <p className="sgt-m">{match.reason}</p> : null}
      <div className="simcrew">
        <CrewFaces
          people={idea.crew_faces.map((p) => ({ name: p.name, initials: p.initials }))}
          total={idea.crew_count}
        />
      </div>
      <div className="simacts">
        <Button
          variant="text"
          aria-label={C.previewOf(idea.title)}
          aria-haspopup="dialog"
          onClick={onPreview}
        >
          {C.preview}
        </Button>
        {action.kind === "team-up" ? (
          <Button size="sm" aria-label={C.teamUpOn(idea.title)} onClick={onTeamUp}>
            {C.teamUp}
          </Button>
        ) : action.kind === "waiting" ? (
          <span className="ck-wait">
            <span className="tuwait">{action.label}</span>
            <Button
              variant="text-blue"
              busy={busy}
              onClick={async () => {
                setBusy(true);
                await onWithdraw(action);
                setBusy(false);
              }}
            >
              {C.withdraw}
            </Button>
          </span>
        ) : (
          <span className="ck-crew">{C.onCrew}</span>
        )}
      </div>
    </li>
  );
}
