import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";

import { Compose } from "./compose";
import "./compose.css";

export const metadata: Metadata = { title: "Share a problem" };
export const dynamic = "force-dynamic";

/** S-04, Tell it (a new problem): `/share` (P-ROUTES). `?new=1` is "Start a new one instead" from a saved draft. */
export default async function TellIt({ searchParams }: { searchParams: Promise<{ new?: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  const { new: fresh } = await searchParams;
  return <Compose firstName={firstName} draftId={null} startNew={fresh === "1"} />;
}
