import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { PausedBanners } from "@/components/banners";
import { DsRuntime } from "@/components/ds-runtime";
import { MainNav } from "@/components/nav";
import { SparkMark } from "@/components/spark-mark";
import { currentUser } from "@/server/auth/current";

import "./globals.css";
import "./ds-tokens.css";
import "./ds.css";
import "./ds-app.css";

export const metadata: Metadata = {
  title: { default: "1% Club", template: "%s · 1% Club" },
  description: "1% Club, a KFintech programme. Share a problem, a fix or a business idea.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

/**
 * The shell (DEC-099): a matte stage, a floating dark-glass dock with the mark, the menu for your roles and the
 * account, the paused-feature bands, and the footer. Working screens are the White surface; brand pages set
 * data-theme="zed" on their own bands. data-tier is 0 here; a One's own pages set their tier on their regions.
 */
export default async function RootLayout({ children }: { children: ReactNode }) {
  const me = await currentUser().catch(() => null);
  const showShell = Boolean(me?.privacyAccepted);
  return (
    <html lang="en-IN" data-theme="white" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="stage" data-tier="0">
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <header className="hdr site-header">
          <div className="hdr-dock dock" data-refract="26" data-dispersion="0.12">
            <Link href="/" className="hdr-brand">
              <SparkMark height={28} />
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
        <DsRuntime />
      </body>
    </html>
  );
}
