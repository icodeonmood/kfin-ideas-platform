import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";

import { PausedBanners } from "@/components/banners";
import { Handover } from "@/components/motion/handover";
import { FOLD_COOKIE, foldedFrom } from "@/components/shell/fold";
import { ShellFrame } from "@/components/shell/frame";
import { currentUser } from "@/server/auth/current";
import { shellData } from "@/server/shell";

import "@fontsource-variable/inter";
import "@fontsource-variable/inter-tight";
import "./tokens.css";
import "./foundation.css";
import "./globals.css";
import "./offer.css";
import "./shell.css";
import "./components.css";
import "./motion.css";
import "./ds-app.css";

export const metadata: Metadata = {
  title: { default: "1% Club", template: "%s · 1% Club" },
  description:
    "1% Club, a KFintech programme. Share a problem in your own words and follow it until it's fixed.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover" };

/**
 * The document and the shell (F-SPACE.shell; C-SIDEBAR, C-PHONE-TABS; BLD-D011). The shell itself is chosen by path in
 * ShellFrame: none on the wall displays, a brand row when signed out, the sidebar and the phone tab bar when signed in.
 * Inter and Inter Tight are self-hosted (BLD-D008). #mo-fx is the motion effects layer (F-MOTION), never interactive.
 */
export default async function RootLayout({ children }: { children: ReactNode }) {
  const me = await currentUser().catch(() => null);
  const signedIn = Boolean(me?.privacyAccepted);
  if (!me) {
    // Signed out (S-01 Landing, S-02 Sign in, signed out): no shell. Each of these pages draws its own top row,
    // its own <main id="main"> and its own footer, as its board does. The wall displays send a signed-out viewer to
    // sign in, so ShellFrame's public frame is only for a signed-in person who has not yet accepted the notice.
    return (
      <html lang="en-IN" data-theme="white">
        <body className="stage">
          <a className="skip-link" href="#main">
            Skip to main content
          </a>
          {children}
        </body>
      </html>
    );
  }
  const data = signedIn ? await shellData(me) : null;
  const folded = foldedFrom((await cookies()).get(FOLD_COOKIE)?.value, me.id);
  return (
    <html lang="en-IN" data-theme="white" data-fold={folded === null ? "auto" : folded ? "folded" : "open"}>
      <body className="stage">
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <ShellFrame
          signedIn={signedIn}
          personId={me?.id ?? null}
          nav={me?.nav ?? []}
          data={data}
          folded={folded}
          banners={signedIn ? <PausedBanners /> : null}
        >
          {children}
        </ShellFrame>
        <div id="mo-fx" aria-hidden="true" />
        <Handover />
      </body>
    </html>
  );
}
