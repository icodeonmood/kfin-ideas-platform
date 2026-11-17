import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { inboxFor, isTab } from "@/server/inbox";

import { InboxReader } from "./inbox-reader";
import { InboxUnavailable } from "./unavailable";
import "./inbox.css";

export const metadata: Metadata = { title: "Inbox" };
export const dynamic = "force-dynamic";

/** S-H5: the one list of what waits on the person and what changed (L-INBOX). `?tab=` opens a tab. */
export default async function Inbox({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const asked = (await searchParams).tab;
  const tab = isTab(asked) ? asked : "all";
  const list = await inboxFor(me, tab).catch(() => null);
  if (!list) return <InboxUnavailable />;
  return <InboxReader initial={list} initialTab={tab} initialItem={null} />;
}
