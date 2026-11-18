import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { composeFlags } from "@/server/flag-events";

import { Compose } from "./compose";
import "./compose.css";

export const metadata: Metadata = { title: "Share a problem" };
export const dynamic = "force-dynamic";

/** S-04, Tell it (a new problem): `/share` (P-ROUTES). `?new=1` is "Start a new one instead" from a saved draft.
 * The S1 and S3 variants come from lane A's reader on the server, which logs the exposure as the screen renders
 * (P-DECISIONS.experiments, BLD-A216, BLD-C170); a flag never fails the page. */
export default async function TellIt({ searchParams }: { searchParams: Promise<{ new?: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  const { new: fresh } = await searchParams;
  const flags = await composeFlags(me, "S-04");
  return <Compose firstName={firstName} draftId={null} startNew={fresh === "1"} flags={flags} />;
}
