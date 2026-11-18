import type { Metadata } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { firstHomeVisit } from "@/server/home";
import { channels } from "@/server/ways";

import { HomeScreen } from "./home";
import "../share/compose.css";
import "./home.css";

export const metadata: Metadata = { title: "Home" };
export const dynamic = "force-dynamic";

/** S-03 Home: `/home` (P-ROUTES.screens), the first screen after sign-in (BLD-C143). */
export default async function Home() {
  const me = await currentUser();
  if (!me) redirect("/sign-in?next=%2Fhome"); // the proxy signs people in first; this is for type narrowing
  const firstName = me.name.trim().split(/\s+/)[0] ?? me.name;
  const prefetch = (await headers()).get("next-router-prefetch") === "1";
  const [firstVisit, ways] = await Promise.all([firstHomeVisit(me, prefetch), channels().catch(() => null)]);
  return (
    <HomeScreen
      firstName={firstName}
      firstVisit={firstVisit}
      outlookAddress={ways?.email.on ? ways.email.address : null}
    />
  );
}
