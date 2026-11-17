import type { Metadata } from "next";
import { redirect } from "next/navigation";

import type { DeskResponse, DeskSort, DeskTab } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { deskRead } from "@/server/desk";

import { DeskView } from "./desk-view";
import "./desk.css";

export const metadata: Metadata = { title: "Review desk" };
export const dynamic = "force-dynamic";

const TABS: readonly DeskTab[] = ["to_review", "waiting", "answered", "decided"];
const SORTS: readonly DeskSort[] = ["time_left", "decide_by", "area"];

/** S-R1 Review desk: what to open next, and every clock that is running. Tab, sort and search live in the URL, so
 * Back restores them (S-R1.rules/4). */
export default async function DeskPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const sp = await searchParams;
  const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : undefined);
  const tab = TABS.find((t) => t === one("tab")) ?? "waiting";
  const sort = SORTS.find((s) => s === one("sort")) ?? "time_left";
  const q = one("q")?.slice(0, 200) ?? "";
  const data = await deskRead<DeskResponse>(me, "/internal/desk", { tab, sort, q });
  if (!data) redirect("/");
  return <DeskView initial={data} initialQuery={q} />;
}
