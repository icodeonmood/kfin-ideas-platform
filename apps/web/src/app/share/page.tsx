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
      <h1>Share an idea</h1>
      <p className="lead">
        Tell us about a problem you face, a fix you have thought of, or a new business idea. A missing answer
        never stops you sharing.
      </p>
      <StartButtons />
      {drafts.length ? (
        <section aria-labelledby="drafts-title">
          <h2 id="drafts-title">Your drafts</h2>
          <p className="muted">Drafts save as you type and are kept for 30 days.</p>
          <ul>
            {drafts.map((d) => (
              <li key={d.id}>
                <Link href={`/share/${d.id}`}>
                  {d.capture_mode === "quick" ? "Quick capture" : "Full canvas"}, last saved{" "}
                  {new Date(d.updated_at).toLocaleString("en-IN", {
                    dateStyle: "medium",
                    timeStyle: "short",
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
