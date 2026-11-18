import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { CrewScreen } from "@/app/crew/crew-screen";
import { isProductionLike } from "@/server/config";

export const metadata: Metadata = { title: "Find your crew kit" };
export const dynamic = "force-dynamic";

/**
 * Find your crew on its own (S-H2, lane F): the same screen as /crew, so e2e can check it in a real browser at phone
 * width with the crew, team-up and preview calls answered by the spec itself (made-up content, no seeded ideas).
 * Dev and test only, like the kit; it does not exist in UAT or production.
 */
export default function CrewKit() {
  if (isProductionLike()) notFound();
  return <CrewScreen />;
}
