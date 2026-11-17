import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { inviteView } from "@/server/ones";

import { WriteForm } from "./write-form";

// No board draws this page (BLD-E042 keeps it; S-ONE's "Messages for you" reads what it saves)
// NOT DRAWN (BLD-E044): HR sign-off
const TITLE = "A few words for a One";
// NOT DRAWN (BLD-E044): HR sign-off
const NOT_OPEN = "This invitation isn't open, or isn't for you.";
// NOT DRAWN (BLD-E044): HR sign-off
const BACK_HOME = "Back to home";
// NOT DRAWN (BLD-E044): HR sign-off
const titleFor = (one: string) => `A few words for ${one}`;
// NOT DRAWN (BLD-E044): HR sign-off
const movingTo = (tier: string) =>
  `They are moving to ${tier}. They'll read your message, with your name, when they see their new tier.`;
// NOT DRAWN (BLD-E044): HR sign-off
const SAVED = "Thank you. Your message is saved.";

export const metadata: Metadata = { title: TITLE };
export const dynamic = "force-dynamic";

/** Where an invited colleague, the CEO or the committee writes a message for a One's tier change (DEC-084). */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  const view = await inviteView(me, id).catch(() => null);
  if (!view) {
    return (
      <>
        <h1>{TITLE}</h1>
        <p className="notice">
          {NOT_OPEN} <Link href="/">{BACK_HOME}</Link>
        </p>
      </>
    );
  }
  return (
    <>
      <h1>{titleFor(view.one_display)}</h1>
      <p className="lead">{movingTo(view.tier_to_name)}</p>
      {view.written ? (
        <p className="notice">{SAVED}</p>
      ) : (
        <WriteForm proposalId={id} as={view.as ?? "peer"} />
      )}
    </>
  );
}
