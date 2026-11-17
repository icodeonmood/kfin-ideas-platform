import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { secondsPerOne, starStyle } from "@/lib/display";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { officeScreen } from "@/server/display";

import { OfficeScreen } from "./office";

import "../display.css";
import "./office.css";

export const metadata: Metadata = { title: "The Ones, in the sky" };
export const dynamic = "force-dynamic";

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * S-OFFICE: the office wall display (L-DISPLAY.office). For the display role, and admins until that role can be
 * granted (BLD-A190). Each screen sets its own pace and background on its address (BLD-A191):
 * `/display/office?seconds=8&stars=dots`.
 */
export default async function Page({ searchParams }: { searchParams: Search }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "open_display")) redirect("/");
  const query = await searchParams;
  const data = await officeScreen().catch(() => null); // the screen fills in on its next refresh
  return (
    <OfficeScreen initial={data} seconds={secondsPerOne(query.seconds)} stars={starStyle(query.stars)} />
  );
}
