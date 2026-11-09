import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { PausedBanners } from "@/components/banners";
import { MainNav } from "@/components/nav";
import { SparkMark } from "@/components/spark-mark";
import { currentUser } from "@/server/auth/current";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "1% Club", template: "%s · 1% Club" },
  description: "1% Club, a KFintech programme. Share a problem, a fix or a business idea.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: ReactNode }) {
  const me = await currentUser().catch(() => null);
  const showShell = Boolean(me?.privacyAccepted);
  return (
    <html lang="en-IN" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <header className="site-header">
          <div className="inner">
            <Link href="/" className="lockup">
              <SparkMark height={28} />
              1% Club
            </Link>
            {showShell && me ? <MainNav items={me.nav} /> : null}
            {me ? (
              <div className="account">
                <span className="account-name">{me.name}</span>
                <form method="post" action="/auth/logout">
                  <button type="submit" className="link-button">
                    Sign out
                  </button>
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
            <p>A KFintech programme</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
