"use client";
/**
 * Home's crew card (S-03.sections/3, C-CREW-DECK.card without "They're looking for", BLD-C146). The data is lane F's
 * `CrewCard` from `GET /api/crew?limit=3` (A-API.team-up, `CrewDeckResponse`), already private by DEC-104: a lead
 * who hid their name or has left is "A colleague" with no user id and no initials, the title is masked and "The
 * problem, in their words" is one checked sentence. The card shows only what that card carries. "Team up on
 * {title}, with {lead}" opens lane F's team-up sheet. Lane F's own card on S-H2 is not exported and says more (the
 * looking-for line, Waiting for), so Home keeps this one; nothing here writes under lane F's paths.
 *
 * DEC-126 (WF-03b, BLD-C219): a card the person has asked to join (`card.request`, from the server after a reload or
 * set by Home after a send) draws lane F's `RequestedAction` where "Team up" was: "Requested", greyed and inactive
 * but focusable and read out, with "Withdraw" under it. S-H2 draws the same component, so the two screens match.
 * "Team up" carries `teamUpOpener(card.id)`, as "Requested" does, so the sheet's focus comes back to whichever of the
 * two stands there, and focus moves to "Team up" after a withdraw.
 */
import { RequestedAction } from "@/components/teamup/requested-action";
import { teamUpOpener, type TeamUpSent } from "@/components/teamup/teamup-sheet";
import { CrewFaces } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { StatusPill, IDEA_STATUS, type IdeaStatus } from "@/components/ui/pill";
import type { CrewCard, PersonRef } from "@/lib/contracts";

function Spark() {
  return (
    <svg width="14" height="17" viewBox="0 0 200 240" aria-hidden="true" focusable="false">
      <polygon points="34,236 146.9,27.2 169.1,40.8" fill="currentColor" />
      <circle cx="171.6" cy="11.8" r="14" fill="currentColor" />
    </svg>
  );
}

function TeamUpIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19c.6-3 2.8-5 5.5-5 1.4 0 2.6.5 3.6 1.4" />
      <path d="M18 14v6M15 17h6" />
    </svg>
  );
}

/**
 * Whether a person on a card is shown as "A colleague" (DEC-104: hid their name from the Wall, or has left).
 * `CrewCard` and `PersonRef` carry no field that says so; the worker's `similar.preview.hidden_person`, which lane F's
 * deck uses, gives such a person no initials (and a name of "A colleague"), and lane F's own card reads it the same
 * way (`leadFirst`). Read from empty initials until the contract marks it.
 */
export function shownAsColleague(p: Pick<PersonRef, "initials">): boolean {
  return !p.initials;
}

/** "Team up on Rejection SMS codes confuse investors, with Ravi Nair" (PhoneHome.md Controls); a lead shown as "A
 * colleague" reads "with a colleague" mid-sentence. */
export function teamUpName(card: Pick<CrewCard, "title" | "lead">): string {
  const lead = shownAsColleague(card.lead) ? card.lead.name.toLowerCase() : card.lead.name;
  return `Team up on ${card.title}, with ${lead}`;
}

/**
 * After a send (DEC-126 (1), (2)): the card asked about carries its request and goes to the end of the deck, where the
 * server keeps it after a reload (BLD-F094). The other cards keep their order. Unchanged when the card is not there.
 */
export function requestedLast(top: CrewCard[], sent: Pick<TeamUpSent, "ideaId" | "id" | "kind">): CrewCard[] {
  const card = top.find((c) => c.id === sent.ideaId);
  if (!card) return top;
  return [...top.filter((c) => c.id !== sent.ideaId), { ...card, request: { id: sent.id, kind: sent.kind } }];
}

/** After a withdraw (DEC-126 (4)): the card drops its request where it stands; no card moves. */
export function requestDropped(top: CrewCard[], ideaId: string): CrewCard[] {
  if (!top.some((c) => c.id === ideaId && c.request)) return top;
  return top.map((c) => (c.id === ideaId ? { ...c, request: undefined } : c));
}

export function CrewCardView({
  card,
  onTeamUp,
  onWithdrawn,
}: {
  card: CrewCard;
  onTeamUp(ideaId: string): void;
  /** After "Withdraw" under "Requested" (DEC-126 (4)): the host drops `card.request` in place. */
  onWithdrawn?(sent: TeamUpSent): void;
}) {
  const status = (card.status in IDEA_STATUS ? card.status : "with_review_desk") as IdeaStatus;
  const everyone = [card.lead, ...card.crew_faces.filter((p) => p.id !== card.lead.id)];
  // A face only for someone with initials: "A colleague" would be an empty circle that still takes focus. They are
  // still counted, so the line reads "A colleague and 2 others on it".
  const people = everyone
    .filter((p) => !shownAsColleague(p))
    .map((p) => ({ name: p.name, initials: p.initials }));
  return (
    <article className={`card hm-pcard hue${card.hue === 2 ? 2 : 1}`} aria-label={card.title}>
      <div className="hm-pc-top">
        <StatusPill status={status} />
        <h3 className="h3 hm-pc-t">{card.title}</h3>
        <p className="meta">{[card.area, card.city].filter(Boolean).join(", ")}</p>
      </div>
      {card.reason ? (
        <p className="hm-pc-why">
          <Spark />
          <span>{card.reason}</span>
        </p>
      ) : null}
      <div className="hm-pc-q">
        <p className="label">The problem, in their words</p>
        <p className="body">{card.in_their_words}</p>
      </div>
      <div className="hm-pc-foot">
        <CrewFaces
          people={people}
          total={Math.max(card.crew_count, everyone.length)}
          leadName={card.lead.name}
        />
        {card.request ? (
          // DEC-126: "Requested" in Team up's look and place, with "Withdraw" under it (lane F's component).
          <RequestedAction
            ideaId={card.id}
            title={card.title}
            request={card.request}
            variant="primary"
            size="full"
            onWithdrawn={(sent) => onWithdrawn?.(sent)}
          />
        ) : (
          <Button
            variant="primary"
            size="full"
            aria-label={teamUpName(card)}
            icon={<TeamUpIcon />}
            onClick={() => onTeamUp(card.id)}
            {...teamUpOpener(card.id)}
          >
            Team up
          </Button>
        )}
      </div>
    </article>
  );
}
