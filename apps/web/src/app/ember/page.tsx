import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { emberArchive } from "@/server/ember";

export const metadata: Metadata = { title: "The Ember" };
export const dynamic = "force-dynamic";

/** The Ember's archive (DEC-062): every issue that has gone out, newest first. */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const data = await emberArchive().catch(() => null);
  return (
    <>
      <div className="brand-band">
        <h1>The Ember</h1>
        <p className="lead">Every month: what the Ones built, what shipped and what it changed.</p>
      </div>
      {can(me.roles, "write_ember_note") ? (
        <p>
          <Link href="/ember/compose">Work on this month&apos;s issue</Link>
        </p>
      ) : null}
      {data === null ? (
        <p className="notice">We can&apos;t load past issues just now. Please try again in a minute.</p>
      ) : data.issues.length ? (
        <ul className="plain-list">
          {data.issues.map((i) => (
            <li key={i.id}>
              <Link href={`/ember/${i.id}`}>The Ember, {i.month_label}</Link>{" "}
              <span className="muted">Sent {day(i.sent_at)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>The first issue goes out at the end of the month.</p>
      )}
    </>
  );
}
