import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { workingGroupItem, type WorkingGroupItem } from "@/server/clusters";
import { SubmissionError } from "@/server/submissions";

export const metadata: Metadata = { title: "Form a working group" };
export const dynamic = "force-dynamic";

export default async function WorkingGroupTrigger({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  let item: WorkingGroupItem;
  try {
    item = await workingGroupItem((await params).id);
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  return (
    <>
      <p>
        <Link href="/review">Back to the queue</Link>
      </p>
      <h1>Form a working group for {item.cluster_id}</h1>
      <section aria-labelledby="wg-why" className="panel">
        <h2 id="wg-why">Why this is here</h2>
        <p>
          {item.contributors} colleagues from {item.lobs.length} LOBs raised the same problem, so the group is
          big enough for a working group.
        </p>
        <p>LOBs: {item.lobs.join(", ") || "—"}</p>
      </section>
      <p className="notice">
        Coming soon: forming the working group from this screen, with suggestions of colleagues already
        working on related groups.
      </p>
    </>
  );
}
