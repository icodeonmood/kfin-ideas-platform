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
  let base: URL;
  try {
    base = appBaseUrl();
  } catch {
    // Never a QR code for an address we don't know (review A1): tell the admin what to fix instead.
    return (
      <div className="launch">
        <div className="launch-intro">
          <h1>Launch screen</h1>
          <p role="alert">
            APP_BASE_URL is not set, so there is no address to put in the QR code. Ask IT to set it to the
            address people should open, then reload this page.
          </p>
        </div>
      </div>
    );
  }
  const url = base.toString();
  const shown = `${base.host}${base.pathname === "/" ? "" : base.pathname}`;
  return <LaunchStage url={url} shownUrl={shown} qr={qrPath(url)} />;
}
