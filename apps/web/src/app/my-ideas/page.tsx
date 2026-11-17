import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import type { MyIdeasResponse } from "@/lib/contracts/api";
import { currentUser } from "@/server/auth/current";
import { getMyIdeas } from "@/server/idea-page";

import { MyIdeasScreen } from "./my-ideas-screen";

import "./my-ideas.css";

export const metadata: Metadata = { title: "My ideas" };
export const dynamic = "force-dynamic";

const KEYS = ["list", "filter", "sort", "q", "row"] as const;

/**
 * S-07, My ideas (copy: reference/copy/MyIdeas.md, PhoneMyIdeas.md; data A-API.my-ideas). The list state lives in
 * the URL (P-ROUTES.state): tab, filter, sort and search are read here and the server returns that exact view, so a
 * shared link reproduces it for whoever opens it, with their own ideas (J-BROWSE/6). Every change on the screen
 * replaces the URL and this page renders the new view.
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
    const res = await getMyIdeas(new NextRequest(new URL(`/api/me/ideas?${q.toString()}`, "http://web.local")));
    if (res.ok) data = (await res.json()) as MyIdeasResponse;
  } catch {
    data = null;
  }
  return <MyIdeasScreen data={data} />;
}
