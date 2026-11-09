import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PrintButton } from "@/components/print-button";
import { ShowcaseView } from "@/components/showcase-view";
import { day } from "@/lib/dates";
import { currentUser } from "@/server/auth/current";
import { myShowcase } from "@/server/ones";

import { ShowcaseForm } from "./showcase-form";

export const metadata: Metadata = { title: "Your Showcase brief" };
export const dynamic = "force-dynamic";

/** A One fills in their Showcase brief (DEC-086); the committee sees it before the Showcase. */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const brief = await myShowcase(me).catch(() => null);
  if (!brief) {
    return (
      <>
        <h1>Your Showcase brief</h1>
        <p className="notice">
          The Showcase brief is for Ones. <Link href="/my-ideas">Back to My ideas</Link>
        </p>
      </>
    );
  }
  return (
    <>
      <h1>Your Showcase brief</h1>
      <p className="lead">
        Thirty minutes at The Showcase, in seven parts. Parts you leave empty show what your record says. The
        core committee reads this before the event.
        {brief.updated_at ? ` Last saved ${day(brief.updated_at)}.` : ""}
      </p>
      <ShowcaseForm brief={brief} />
      <h2>How it reads</h2>
      <PrintButton />
      <ShowcaseView brief={brief} />
    </>
  );
}
