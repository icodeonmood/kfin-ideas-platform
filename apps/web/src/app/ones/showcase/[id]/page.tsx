import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PrintButton } from "@/components/print-button";
import { ShowcaseView } from "@/components/showcase-view";
import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { showcaseFor } from "@/server/ones";

export const metadata: Metadata = { title: "Showcase brief" };
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
        We can&apos;t find that Showcase brief. <Link href="/wall">Back to the Wall</Link>
      </p>
    );
  }
  return (
    <>
      <p className="no-print">
        <Link href="/wall">Back to the Wall</Link>
      </p>
      <h1>
        Showcase brief: No. {brief.number ?? "retired"}, {brief.name}
      </h1>
      <p className="lead">
        Tier {brief.tier}, {brief.tier_name}.{" "}
        {brief.updated_at
          ? `The One last updated it ${day(brief.updated_at)}.`
          : "The One hasn't added their own words yet."}
      </p>
      <PrintButton />
      <ShowcaseView brief={brief} />
    </>
  );
}
