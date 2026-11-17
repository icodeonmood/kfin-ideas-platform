import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PrintButton } from "@/components/print-button";
import { ShowcaseView } from "@/components/showcase-view";
import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { showcaseFor } from "@/server/ones";

// No board draws this page (BLD-E042 keeps it for the committee, ready to print)
// NOT DRAWN (BLD-E044): HR sign-off
const TITLE = "Showcase brief";
// NOT DRAWN (BLD-E044): HR sign-off
const NOT_FOUND = "We can't find that Showcase brief.";
// NOT DRAWN (BLD-E044): HR sign-off
const BACK_TO_WALL = "Back to the Wall";
// NOT DRAWN (BLD-E044): HR sign-off
const heading = (number: number | null, name: string) =>
  `Showcase brief: No. ${number ?? "retired"}, ${name}`;
// NOT DRAWN (BLD-E044): HR sign-off
const tierLine = (tier: number, tierName: string) => `Tier ${tier}, ${tierName}.`;
// NOT DRAWN (BLD-E044): HR sign-off
const updatedOn = (when: string) => `The One last updated it ${when}.`;
// NOT DRAWN (BLD-E044): HR sign-off
const NO_WORDS_YET = "The One hasn't added their own words yet.";

export const metadata: Metadata = { title: TITLE };
export const dynamic = "force-dynamic";

/** A One's Showcase brief for the committee, ready to print (DEC-086). */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "view_ones_console")) redirect("/");
  const brief = await showcaseFor((await params).id).catch(() => null);
  if (!brief) {
    return (
      <p className="notice">
        {NOT_FOUND} <Link href="/wall">{BACK_TO_WALL}</Link>
      </p>
    );
  }
  return (
    <>
      <p className="no-print">
        <Link href="/wall">{BACK_TO_WALL}</Link>
      </p>
      <h1>{heading(brief.number, brief.name)}</h1>
      <p className="lead">
        {tierLine(brief.tier, brief.tier_name)}{" "}
        {brief.updated_at ? updatedOn(day(brief.updated_at)) : NO_WORDS_YET}
      </p>
      <PrintButton />
      <ShowcaseView brief={brief} />
    </>
  );
}
