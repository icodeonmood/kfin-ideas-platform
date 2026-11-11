import type { Metadata } from "next";
import Link from "next/link";

import { currentUser } from "@/server/auth/current";
import { getDb } from "@/server/db";

import { StartButtons } from "./start";

export const metadata: Metadata = { title: "Share an idea" };
export const dynamic = "force-dynamic";

export default async function Share() {
  const me = await currentUser();
  const drafts = me?.contributorCode
    ? await getDb()
        .selectFrom("ideas")
        .select(["id", "capture_mode", "updated_at"])
        .where("contributor_code", "=", me.contributorCode)
        .where("stage", "=", "draft")
        .orderBy("updated_at", "desc")
        .limit(10)
        .execute()
    : [];
  return (
    <>
      <h1 className="t-display page-display">Share an idea</h1>
      <p className="lead page-lead">
        Tell us about a problem you face, a fix you have thought of, or a new business idea. A missing answer
        never stops you sharing.
      </p>
      <StartButtons />
      {drafts.length ? (
        <section className="drafts" aria-labelledby="drafts-title">
          <h2 id="drafts-title" className="t-h2">
            Your drafts
          </h2>
          <p className="muted">Drafts save as you type and are kept for 30 days.</p>
          <ul className="draft-list">
            {drafts.map((d) => (
              <li key={d.id} className="glass draft-row" data-lit="">
                <Link href={`/share/${d.id}`}>
                  {d.capture_mode === "quick" ? "Quick capture" : "Full canvas"}, last saved{" "}
                  {new Date(d.updated_at).toLocaleString("en-IN", {
                    dateStyle: "medium",
                    timeStyle: "short",
                    timeZone: "Asia/Kolkata", // rendered on the server, which may run in UTC (BLD-A165)
                  })}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
