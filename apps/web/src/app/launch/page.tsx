import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { appBaseUrl } from "@/server/config";
import { qrPath } from "@/server/qr";

import { LaunchStage } from "./stage";

export const metadata: Metadata = { title: "Launch screen" };
export const dynamic = "force-dynamic";

/**
 * The lamp-lighting go-live screen (DEC-046, docs/BRAND.md section 5). Admin only: the person driving the big
 * screen at the inauguration. The QR code points at this environment's own address.
 */
export default async function Launch() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "grant_roles")) redirect("/");
  const base = appBaseUrl();
  const url = base.toString();
  const shown = `${base.host}${base.pathname === "/" ? "" : base.pathname}`;
  return <LaunchStage url={url} shownUrl={shown} qr={qrPath(url)} />;
}
