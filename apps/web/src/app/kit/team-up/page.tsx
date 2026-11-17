import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isProductionLike } from "@/server/config";

import { TeamUpDemo } from "./team-up-demo";

export const metadata: Metadata = { title: "Team up sheet" };
export const dynamic = "force-dynamic";

/**
 * The team-up sheet on its own (C-SHEET-TEAMUP, lane F, BLD-F074): opened from an idea and from a draft on Check it,
 * so e2e can check it in a real browser at phone width before the screens that host it land. The e2e spec answers
 * the sheet's API calls itself. Dev and test only, like the kit; it does not exist in UAT or production.
 */
export default function TeamUpKit() {
  if (isProductionLike()) notFound();
  return <TeamUpDemo />;
}
