import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { inboxFor } from "@/server/inbox";

import { itemIn, readInboxAddress } from "./address";
import { InboxReader } from "./inbox-reader";
import { InboxUnavailable } from "./unavailable";
import "./inbox.css";

export const metadata: Metadata = { title: "Inbox" };
export const dynamic = "force-dynamic";

type Query = Record<string, string | string[] | undefined>;

/** S-H5: the one list of what waits on the person and what changed (L-INBOX). The address names the tab and the open
 * item (`?tab=needs_you&item=41`, P-ROUTES.state), so a reload or a link shows the same view; an item opens only if
 * it is in the person's own list for that tab, and anything the address gets wrong falls back to the default. */
export default async function Inbox({ searchParams }: { searchParams: Promise<Query> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const asked = readInboxAddress(await searchParams);
  const list = await inboxFor(me, asked.tab).catch(() => null);
  if (!list) return <InboxUnavailable />;
  return <InboxReader initial={list} initialTab={asked.tab} initialItem={itemIn(asked.item, list.items)} />;
}
