import type { Metadata } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import type { MyIdeasResponse } from "@/lib/contracts/api";
import { currentUser } from "@/server/auth/current";
import { getMyIdeas } from "@/server/idea-page";

import { MyIdeasScreen } from "./my-ideas-screen";

import "./my-ideas.css";

export const metadata: Metadata = { title: "My ideas" };
export const dynamic = "force-dynamic";

/** The address's own keys: tab, filter, sort and the row to come back to. Never a search (DEC-110). */
const KEYS = ["list", "filter", "sort", "row"] as const;

/**
 * S-07, My ideas (copy: reference/copy/MyIdeas.md, PhoneMyIdeas.md; data A-API.my-ideas). Tab, filter and sort live
 * in the URL (P-ROUTES.state): they are read here and the server returns that view, so a shared link reproduces it
 * for whoever opens it, with their own ideas (J-BROWSE/6). The search never does (DEC-110): the screen keeps it in
 * this tab's memory of the history entry and asks for the searched view itself, with the words in a request body.
 */
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const me = await currentUser();
  if (!me) redirect("/sign-in?next=%2Fmy-ideas");
  const sp = await searchParams;
  const q = new URLSearchParams();
  for (const k of KEYS) {
    const v = sp[k];
    const one = Array.isArray(v) ? v[0] : v;
    if (one) q.set(k, one.slice(0, 200));
  }
  let data: MyIdeasResponse | null = null;
  try {
    // The real request's headers, so the server render knows this device as the API does ("on this laptop")
    const res = await getMyIdeas(
      new NextRequest(new URL(`/api/me/ideas?${q.toString()}`, "http://web.local"), {
        headers: await headers(),
      }),
    );
    if (res.ok) data = (await res.json()) as MyIdeasResponse;
  } catch {
    data = null;
  }
  return <MyIdeasScreen data={data} />;
}
