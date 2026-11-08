/**
 * One idea or cluster as everyone may see it (§4.2 step 7, §4.13): the neutral summary, area, stage and the
 * number of colleagues on it. Names only on the wall, and only for people who said yes (`public_name_consent`).
 */
import Link from "next/link";

import type { PublicCard } from "@/server/ideas";

function people(card: PublicCard): string | null {
  const names = card.names ?? [];
  if (!names.length) return null;
  const others = Math.max(0, card.colleagues - names.length);
  return others ? `${names.join(", ")} and ${others} more` : names.join(", ");
}

export function IdeaCard({ card, headingLevel = 3 }: { card: PublicCard; headingLevel?: 2 | 3 }) {
  const H = headingLevel === 2 ? "h2" : "h3";
  const by = people(card);
  return (
    <li className="crew-card">
      <H>{card.idea_id ? <Link href={`/ideas/${card.idea_id}`}>{card.summary}</Link> : card.summary}</H>
      <dl className="crew-facts">
        {card.area ? (
          <div>
            <dt>Area</dt>
            <dd>{card.area}</dd>
          </div>
        ) : null}
        <div>
          <dt>Where it is</dt>
          <dd>{card.stage}</dd>
        </div>
        <div>
          <dt>Colleagues on it</dt>
          <dd>{card.colleagues}</dd>
        </div>
        {by ? (
          <div>
            <dt>Shared by</dt>
            <dd>{by}</dd>
          </div>
        ) : null}
      </dl>
    </li>
  );
}
