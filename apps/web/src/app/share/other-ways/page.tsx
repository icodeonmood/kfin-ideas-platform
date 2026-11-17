import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { arrivals, channels, wantsAppNews } from "@/server/ways";

import { AppNewsButton, CopyAddress } from "./ways";

import "./ways.css";

export const metadata: Metadata = { title: "Share another way" };
export const dynamic = "force-dynamic";

const mailto = (address: string) =>
  `mailto:${encodeURIComponent(address).replace(/%40/g, "@")}?subject=${encodeURIComponent("Fwd: ")}&body=${encodeURIComponent("What gets in the way: ")}`;

function Icon({ kind }: { kind: "mail" | "chat" | "app" }) {
  const common = {
    width: 24,
    height: 24,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  if (kind === "mail")
    return (
      <svg {...common}>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3.5 6.5 8.5 6.5 8.5-6.5" />
      </svg>
    );
  if (kind === "chat")
    return (
      <svg {...common}>
        <path d="M4 5h16v11H9l-5 4z" />
        <path d="M8 9.5h8M8 12.5h5" strokeLinecap="round" />
      </svg>
    );
  return (
    <svg {...common} strokeLinecap="round">
      <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
      <path d="M11 18.5h2" />
    </svg>
  );
}

const Soon = () => (
  <span className="wy-pill">
    <i aria-hidden="true" />
    Coming soon
  </span>
);

/**
 * S-H3 "Share another way": forward from Outlook, message in Teams, the app (coming soon), and what has arrived.
 * Email and Teams are built and switched off until IT approves them (DEC-105): while a way is off its card says
 * "Coming soon" and its address, steps and button are hidden (L-AUDIT.flags), and with both off nothing can
 * arrive, so "Arrived from elsewhere" is not shown (BLD-A192).
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const [ways, arrived, wants] = await Promise.all([channels(), arrivals(me), wantsAppNews(me)]);
  const anyOpen = ways.email.on || ways.teams.on;
  return (
    <div className="wy">
      <Link href="/" className="wy-back">
        <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <path d="M10 3.5 5.5 8l4.5 4.5" />
        </svg>
        Home
      </Link>
      <h1 className="wy-title">Share another way</h1>
      <p className="wy-lead">Each one lands here as a draft. Nothing is sent until you check it.</p>

      <div className="wy-grid">
        <section className="wy-card" aria-labelledby="w-mail">
          <span className="wy-ic wy-ic-mail">
            <Icon kind="mail" />
          </span>
          <h2 id="w-mail" className="wy-h">
            Forward it from Outlook {ways.email.on ? null : <Soon />}
          </h2>
          <p className="wy-meta">
            Forward the thread that shows the problem. Your note on top becomes the draft.
          </p>
          {ways.email.on && ways.email.address ? (
            <>
              <CopyAddress address={ways.email.address} />
              <div className="wy-acts">
                <a className="wy-btn" href={mailto(ways.email.address)}>
                  Open in Outlook
                </a>
              </div>
            </>
          ) : null}
        </section>

        <section className="wy-card" aria-labelledby="w-teams">
          <span className="wy-ic wy-ic-chat">
            <Icon kind="chat" />
          </span>
          <h2 id="w-teams" className="wy-h">
            Message it in Teams {ways.teams.on ? null : <Soon />}
          </h2>
          <p className="wy-meta">Chat with 1% Club in Teams. Paste screenshots straight in.</p>
          {ways.teams.on && ways.teams.link ? (
            <>
              <p className="wy-tsh">First time? Add it once:</p>
              <ol className="wy-steps">
                <li>
                  In Teams, open <b>Apps</b> from the side bar.
                </li>
                <li>
                  Search for <b>1% Club</b> under Built for your org, and select <b>Add</b>.
                </li>
                <li>
                  Right-click it in the side bar and select <b>Pin</b>, so it stays there.
                </li>
              </ol>
              <div className="wy-acts">
                <a className="wy-btn" href={ways.teams.link} rel="noopener noreferrer">
                  Open in Teams
                </a>
              </div>
            </>
          ) : null}
        </section>

        <section className="wy-card" aria-labelledby="w-app">
          <span className="wy-ic wy-ic-app">
            <Icon kind="app" />
          </span>
          <h2 id="w-app" className="wy-h">
            Use the 1% Club app <Soon />
          </h2>
          <p className="wy-meta">Share from your phone, typed or spoken, in any language.</p>
          <p className="wy-plat">Android and iOS</p>
          <div className="wy-acts">
            <AppNewsButton initial={wants} />
          </div>
        </section>
      </div>

      {anyOpen ? (
        <section className="wy-arr" aria-labelledby="arr-h">
          <div className="wy-arr-h">
            <h2 id="arr-h" className="wy-h">
              Arrived from elsewhere
            </h2>
            {arrived.length ? <span className="wy-meta">{arrived.length} to check</span> : null}
          </div>
          {arrived.length ? (
            arrived.map((a) => (
              <div key={a.draft_id} className="wy-row">
                <span className="wy-src">
                  <Icon kind={a.channel === "email" ? "mail" : "chat"} />
                </span>
                <div>
                  <p className="wy-row-t">{a.title}</p>
                  <p className="wy-meta">{a.detail}</p>
                </div>
                <Link className="wy-btn" href={`/share/${encodeURIComponent(a.draft_id)}`}>
                  Check and send
                </Link>
              </div>
            ))
          ) : (
            <p className="wy-meta wy-none">Nothing waiting. Anything you forward or message shows up here.</p>
          )}
        </section>
      ) : null}
    </div>
  );
}
