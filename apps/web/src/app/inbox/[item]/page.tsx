import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { inboxFor, isItemId } from "@/server/inbox";

import { itemIn, readInboxAddress } from "../address";
import { InboxReader } from "../inbox-reader";
import { InboxUnavailable } from "../unavailable";
import "../inbox.css";

export const metadata: Metadata = { title: "Inbox" };
export const dynamic = "force-dynamic";

type Query = Record<string, string | string[] | undefined>;

/** S-H2B and every Inbox link to one item (`/inbox/:itemId`): the Inbox with that item open, on the tab that holds
 * it. An item that is not the person's opens the Inbox as it is. Once the person moves on this page the reader adds
 * the view to the query (`?tab=…&item=…`, J-BROWSE/4), and the query is then the view, as on `/inbox`. */
export default async function InboxItemPage({
  params,
  searchParams,
}: {
  params: Promise<{ item: string }>;
  searchParams: Promise<Query>;
}) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const { item } = await params;
  if (!isItemId(item)) redirect("/inbox");
  const asked = readInboxAddress(await searchParams);
  if (asked.named) {
    const list = await inboxFor(me, asked.tab).catch(() => null);
    if (!list) return <InboxUnavailable />;
    return <InboxReader initial={list} initialTab={asked.tab} initialItem={itemIn(asked.item, list.items)} />;
  }
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
