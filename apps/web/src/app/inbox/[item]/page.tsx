import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { inboxFor, isItemId } from "@/server/inbox";

import { InboxReader } from "../inbox-reader";
import { InboxUnavailable } from "../unavailable";
import "../inbox.css";

export const metadata: Metadata = { title: "Inbox" };
export const dynamic = "force-dynamic";

/** S-H2B and every Inbox link to one item (`/inbox/:itemId`): the Inbox with that item open, on the tab that holds
 * it. An item that is not the person's opens the Inbox as it is. */
export default async function InboxItemPage({ params }: { params: Promise<{ item: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const { item } = await params;
  if (!isItemId(item)) redirect("/inbox");
  const all = await inboxFor(me, "all").catch(() => null);
  if (!all) return <InboxUnavailable />;
  if (all.items.some((i) => i.id === item)) {
    return <InboxReader initial={all} initialTab="all" initialItem={item} />;
  }
  const archived = await inboxFor(me, "archived").catch(() => null);
  if (archived?.items.some((i) => i.id === item)) {
    return <InboxReader initial={archived} initialTab="archived" initialItem={item} />;
  }
  return <InboxReader initial={all} initialTab="all" initialItem={null} />;
}
