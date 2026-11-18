import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isProductionLike } from "@/server/config";

import { ConversationDemo } from "./conversation-demo";

export const metadata: Metadata = { title: "Conversation" };
export const dynamic = "force-dynamic";

/**
 * S-08, an idea's conversation, with made-up content (lane F, BLD-F066): so e2e can check the screen, its box and
 * the @mention picker in a real browser at phone width with axe, without a seeded idea. The e2e spec answers the
 * screen's calls itself. Dev and test only, like the kit; it does not exist in UAT or production. `?view=questions`
 * shows the sharer's own idea with the review desk's open questions, as lane B's card (BLD-B249); `?view=long` a
 * conversation long enough to open past the fold (BLD-F081).
 */
export default async function ConversationKit({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  if (isProductionLike()) notFound();
  const asked = (await searchParams).view;
  const view = asked === "questions" || asked === "long" ? asked : "crew";
  return <ConversationDemo view={view} />;
}
