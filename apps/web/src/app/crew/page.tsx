import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";

import { CrewScreen } from "./crew-screen";

export const metadata: Metadata = { title: "Find your crew" };
export const dynamic = "force-dynamic";

/** S-H2, Find your crew (lane F): the deck reads `GET /api/crew` from the page, so filters and passes stay live. */
export default async function CrewPage() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  return <CrewScreen />;
}
