import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { composeFlags } from "@/server/flags";

import { Compose } from "./compose";
import "./compose.css";

export const metadata: Metadata = { title: "Share a problem" };
export const dynamic = "force-dynamic";

/** S-04, Tell it (a new problem): `/share` (P-ROUTES). `?new=1` is "Start a new one instead" from a saved draft.
 * The S1 and S3 variants come from the server (P-DECISIONS.experiments, BLD-C170); a flag never fails the page. */
export default async function TellIt({ searchParams }: { searchParams: Promise<{ new?: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  const { new: fresh } = await searchParams;
  const flags = await composeFlags(me.id);
  return <Compose firstName={firstName} draftId={null} startNew={fresh === "1"} flags={flags} />;
}
