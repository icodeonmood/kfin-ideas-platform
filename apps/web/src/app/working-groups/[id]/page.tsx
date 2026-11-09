import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { workingGroup } from "@/server/committee";
import { SubmissionError } from "@/server/submissions";

export const metadata: Metadata = { title: "Working group" };
export const dynamic = "force-dynamic";

type Group = {
  id: string;
  cluster_id: string;
  decision_id: string | null;
  state: string;
  name: string | null;
  sponsor: string | null;
  members: { name: string; role: string }[];
  formed_at: string;
};

export default async function WorkingGroup({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  let g: Group;
  try {
    g = (await workingGroup(me, (await params).id)) as Group;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  return (
    <>
      <h1>
        Working group {g.id}: {g.name ?? g.cluster_id}
      </h1>
      <p className="lead">
        {g.state === "forming" ? "Forming" : g.state}, since{" "}
        {new Date(g.formed_at).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "long",
          timeZone: "Asia/Kolkata",
        })}
        . Sponsor: {g.sponsor ?? "to be named"}.
      </p>
      <section aria-labelledby="wg-members" className="panel">
        <h2 id="wg-members">Members</h2>
        <ul>
          {g.members.map((m, i) => (
            <li key={i}>
              {m.name} ({m.role})
            </li>
          ))}
        </ul>
      </section>
      <p className="notice">
        Coming soon: the charter, protected time agreed with managers, the kick-off invitation and first
        milestones.
      </p>
    </>
  );
}
