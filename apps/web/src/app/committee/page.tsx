import type { Metadata } from "next";
import { redirect } from "next/navigation";

import type { CommitteeResponse, CommitteeSort, CommitteeTab } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { deskRead } from "@/server/desk";
import { promises } from "@/server/promises";

import { CommitteeView } from "./committee-view";
import "../desk/desk.css";
import "./committee.css";

export const metadata: Metadata = { title: "Ones Committee" };
export const dynamic = "force-dynamic";

const TABS: readonly CommitteeTab[] = ["window", "reversed", "expired"];
const SORTS: readonly CommitteeSort[] = ["closing", "decided", "area"];

/** S-R4 Ones Committee: every desk decision for its window; extend, or reverse once with a note (L-COMMITTEE). */
export default async function CommitteePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const sp = await searchParams;
  const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : undefined);
  const tab = TABS.find((t) => t === one("tab")) ?? "window";
  const sort = SORTS.find((s) => s === one("sort")) ?? "closing";
  const [data, p] = await Promise.all([
    deskRead<CommitteeResponse>(me, "/internal/committee", { tab, sort }),
    promises(),
  ]);
  if (!data) redirect("/");
  return (
    <CommitteeView
      initial={data}
      tab={tab}
      sort={sort}
      open={one("open") ?? null}
      noteMin={p.notes.reversal_note_min_chars}
      returnMonths={p.not_now.return_options_months}
    />
  );
}
