import type { Metadata } from "next";
import { redirect } from "next/navigation";

import type { ProfileResponse } from "@/lib/contracts/api";
import { currentUser } from "@/server/auth/current";
import { profile } from "@/server/wall";

import { ProfileScreen } from "./profile-screen";
import { ProfileUnavailable } from "./unavailable";

import "./profile.css";

export const metadata: Metadata = { title: "Profile and settings" };
export const dynamic = "force-dynamic";

/**
 * S-H6, Profile and settings (L-ONES, L-NOTIFY; copy: reference/copy/Profile.md). Always the signed-in person's own,
 * read on the server through the same worker relay as `GET /api/me/profile`. Switches save one at a time through
 * `PATCH /api/me/settings`; "How should we refer to you?" through lane C's `/api/me/refer-as` (DEC-108, BLD-E043).
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in?next=%2Fprofile");
  const res = await profile(me).catch(() => null);
  const body = res?.ok ? ((await res.json().catch(() => null)) as ProfileResponse | null) : null;
  if (!body?.person) return <ProfileUnavailable />;
  return <ProfileScreen data={body} />;
}
