import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "The Garage · Ideas",
  description: "KFintech's ideas platform. Share a problem, a fix or a business idea.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN">
      <body>
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <header className="site-header">
          <div className="inner">
            <p className="lockup">
              The Garage
              <span className="divider" aria-hidden="true">
                ·
              </span>
              Ideas
            </p>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          {children}
        </main>
      </body>
    </html>
  );
}
