import type { Metadata } from "next";
import { redirect } from "next/navigation";

import type { OneDashboardResponse } from "@/lib/contracts/api";
import { currentUser } from "@/server/auth/current";
import { oneDashboard } from "@/server/wall";

import { OneScreen } from "./one-screen";
import { isNotAOne } from "./rules";
import { OneUnavailable } from "./unavailable";

import "./one.css";

export const metadata: Metadata = { title: "Your One dashboard" };
export const dynamic = "force-dynamic";

/**
 * S-ONE, a One's own dashboard (L-ONES, L-IMPACT; copy: reference/copy/OneDashboard.md). Read on the server through
 * the same worker relay as `GET /api/one`, so the page arrives whole. Only a One opens it: anyone else is sent to
 * Profile (S-ONE.rules/1), but only when the worker's 403 says `not_a_one`: any other refusal shows the error state.
 * Reading it changes nothing; a waiting tier moment is marked seen by its own call once it has played (S-ONE.rules/3).
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in?next=%2Fone");
  const res = await oneDashboard(me).catch(() => null);
  const body = res ? ((await res.json().catch(() => null)) as unknown) : null;
  if (isNotAOne(res?.status, body)) redirect("/profile");
  if (!res?.ok || !body) return <OneUnavailable />;
  return <OneScreen data={body as OneDashboardResponse} />;
}
