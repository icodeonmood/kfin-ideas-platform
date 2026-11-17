import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isProductionLike } from "@/server/config";

import { ConversationDemo } from "./conversation-demo";

export const metadata: Metadata = { title: "Conversation" };
export const dynamic = "force-dynamic";

/**
 * S-08, an idea's conversation, with made-up content (lane F, BLD-F066): so e2e can check the screen, its box and
 * the @mention picker in a real browser at phone width with axe, without a seeded idea. The e2e spec answers the
 * screen's calls itself. Dev and test only, like the kit; it does not exist in UAT or production.
 */
export default function ConversationKit() {
  if (isProductionLike()) notFound();
  return <ConversationDemo />;
}
