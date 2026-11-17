import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";

import { loadWall } from "./load";
import { wallState } from "./state";
import { WallScreen } from "./wall-screen";

import "./wall.css";

export const metadata: Metadata = { title: "Wall" };
export const dynamic = "force-dynamic";

/**
 * S-WALL, the Wall (L-WALL; copy: reference/copy/Wall.md and PhoneWall.md). The first view is read on the server so
 * the page arrives whole and a way back (J-BROWSE/5) lands on the same place at once; the kind chip, Just in's sort
 * and "Show 5 more" then fetch `/api/wall/*` in place and keep their state in the URL (P-ROUTES.state).
 */
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const me = await currentUser();
  if (!me) redirect("/sign-in?next=%2Fwall");
  const state = wallState(await searchParams);
  const data = await loadWall(state);
  // A new address from the server (a link, Back) starts the screen afresh from its own data
  return <WallScreen key={JSON.stringify(state)} state={state} data={data} />;
}
