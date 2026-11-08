import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { PausedBanners } from "@/components/banners";
import { MainNav } from "@/components/nav";
import { currentUser } from "@/server/auth/current";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "The Garage · Ideas", template: "%s · The Garage · Ideas" },
  description: "KFintech's ideas platform. Share a problem, a fix or a business idea.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: ReactNode }) {
  const me = await currentUser().catch(() => null);
  const showShell = Boolean(me?.privacyAccepted);
  return (
    <html lang="en-IN">
      <body>
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <header className="site-header">
          <div className="inner">
            <Link href="/" className="lockup">
              The Garage
              <span className="divider" aria-hidden="true">
                ·
              </span>
              Ideas
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
      </body>
    </html>
  );
}
