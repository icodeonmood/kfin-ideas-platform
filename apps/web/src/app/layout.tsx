import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { PausedBanners } from "@/components/banners";
import { MainNav } from "@/components/nav";
import { SparkMark } from "@/components/spark-mark";
import { currentUser } from "@/server/auth/current";

import "@fontsource-variable/inter";
import "@fontsource-variable/inter-tight";
import "./globals.css";
import "./offer.css";
import "./ds-app.css";

export const metadata: Metadata = {
  title: { default: "1% Club", template: "%s · 1% Club" },
  description: "1% Club, a KFintech programme. Share a problem, a fix or a business idea.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

/**
 * The shell in the OFFER theme (DEC-101): the lockup, the menu for your roles and the account on a warm paper ground,
 * the paused-feature bands, and the footer. Inter and Inter Tight are self-hosted from their npm packages (BLD-D008),
 * so no page asks Google for a font. Brand moments set data-theme="zed" on their own dark panel; a One's pages set
 * data-tier on their own regions.
 */
export default async function RootLayout({ children }: { children: ReactNode }) {
  const me = await currentUser().catch(() => null);
  const showShell = Boolean(me?.privacyAccepted);
  if (!me) {
    // Signed out (S-01 Landing, S-02 Sign in, signed out): no shell. Each of these pages draws its own top row,
    // its own <main id="main"> and its own footer, as its board does.
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
  return (
    <html lang="en-IN" data-theme="white">
      <body className="stage">
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <header className="hdr site-header">
          <div className="hdr-dock">
            <Link href="/" className="hdr-brand">
              <SparkMark height={26} />
              1% Club
            </Link>
            {showShell && me ? <MainNav items={me.nav} /> : null}
            {me ? (
              <div className="hdr-end">
                <span className="hdr-name account-name">{me.name}</span>
                <form method="post" action="/auth/logout">
                  <button type="submit">Sign out</button>
                </form>
              </div>
            ) : null}
          </div>
        </header>
        {showShell ? <PausedBanners /> : null}
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <footer className="site-footer">
          <div className="inner">
            <p>1% Club</p>
            {showShell ? (
              <p>
                <Link href="/ember">The Ember</Link>
              </p>
            ) : null}
            <p>A KFintech programme</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
