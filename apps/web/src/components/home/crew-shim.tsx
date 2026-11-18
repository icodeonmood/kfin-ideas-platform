"use client";
/**
 * A stand-in for lane F's crew card (C-CREW-DECK.card) on Home until Find your crew is on main (BLD-C146). Home shows
 * the card without "They're looking for" (S-03.sections/3). The data is lane F's `CrewCard` from `GET /api/crew`
 * (A-API.crew, f/crew-search); `lib/home/data.ts` reads it and the section shows its empty state while the route is
 * not there. When lane F's card is on main, `app/home/home.tsx` renders theirs and this file goes. Never create
 * anything under components/teamup/ or lane F's paths.
 */
import { CrewFaces } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { StatusPill, IDEA_STATUS, type IdeaStatus } from "@/components/ui/pill";
import type { CrewCard } from "@/lib/contracts";

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

/** "Team up on Rejection SMS codes confuse investors, with Ravi Nair" (Home.md Controls). */
export function teamUpName(card: Pick<CrewCard, "title" | "lead">): string {
  return `Team up on ${card.title}, with ${card.lead.name}`;
}

export function CrewCardView({ card, onTeamUp }: { card: CrewCard; onTeamUp(ideaId: string): void }) {
  const status = (card.status in IDEA_STATUS ? card.status : "with_review_desk") as IdeaStatus;
  const people = [card.lead, ...card.crew_faces.filter((p) => p.id !== card.lead.id)].map((p) => ({
    name: p.name,
    initials: p.initials,
  }));
  return (
    <article className={`card hm-pcard h${card.hue === 2 ? 2 : 1}`} aria-label={card.title}>
      <div className="hm-pc-top">
        <StatusPill status={status} />
        <h3 className="h3 hm-pc-t">{card.title}</h3>
        <p className="meta">
          {card.area}, {card.city}
        </p>
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
          total={Math.max(card.crew_count, people.length)}
          leadName={card.lead.name}
        />
        <Button
          size="full"
          aria-label={teamUpName(card)}
          icon={<TeamUpIcon />}
          onClick={() => onTeamUp(card.id)}
        >
          Team up
        </Button>
      </div>
    </article>
  );
}
