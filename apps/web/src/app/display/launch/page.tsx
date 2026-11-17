import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { appBaseUrl } from "@/server/config";
import { qrPath } from "@/server/qr";

import { LaunchScreen } from "./stage";

import "../display.css";
import "./launch.css";

export const metadata: Metadata = { title: "Launch screen" };
export const dynamic = "force-dynamic";

/**
 * S-LAUNCH: the launch screen for the lamp lighting (L-DISPLAY.launch). For the display role, and admins until that
 * role can be granted (BLD-A190); the proxy redirects everyone else home. The QR code is drawn here from the
 * configured sign-in address (L-DISPLAY.launch/3), never from the request.
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "open_display")) redirect("/");
  let base: URL;
  try {
    base = appBaseUrl();
  } catch {
    // Never a QR code for an address we don't know (review A1): tell the operator what to fix instead.
    return (
      <div className="dsp dl">
        <section className="dl-intro">
          <h1 className="dl-title">Launch screen</h1>
          <p className="dl-lead" role="alert">
            APP_BASE_URL is not set, so there is no address to put in the QR code. Ask IT to set it to the
            address people should open, then reload this page.
          </p>
        </section>
      </div>
    );
  }
  const url = base.toString();
  const shown = `${base.host}${base.pathname === "/" ? "" : base.pathname}`;
  return <LaunchScreen url={url} shownUrl={shown} qr={qrPath(url)} />;
}
