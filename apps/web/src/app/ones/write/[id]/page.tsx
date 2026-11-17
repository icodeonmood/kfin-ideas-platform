import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { inviteView } from "@/server/ones";

import { WriteForm } from "./write-form";

export const metadata: Metadata = { title: "A few words for a One" };
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
        <h1>A few words for a One</h1>
        <p className="notice">
          This invitation isn&apos;t open, or isn&apos;t for you. <Link href="/">Back to home</Link>
        </p>
      </>
    );
  }
  return (
    <>
      <h1>A few words for {view.one_display}</h1>
      <p className="lead">
        They are moving to {view.tier_to_name}. They&apos;ll read your message, with your name, when they see
        their new tier.
      </p>
      {view.written ? (
        <p className="notice">Thank you. Your message is saved.</p>
      ) : (
        <WriteForm proposalId={id} as={view.as ?? "peer"} />
      )}
    </>
  );
}
