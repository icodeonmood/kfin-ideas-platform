import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { presentationForContributor } from "@/server/committee";
import { SubmissionError } from "@/server/submissions";

import { Invitation, type ContributorPresentation } from "./invitation";

export const metadata: Metadata = { title: "Your invitation to present" };
export const dynamic = "force-dynamic";

export default async function PresentationInvite({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  let view: ContributorPresentation;
  try {
    view = (await presentationForContributor(me, (await params).id)) as ContributorPresentation;
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  return (
    <>
      <h1>Present {view.name ?? view.cluster_id} to the 1% Club core committee</h1>
      <p className="lead">
        The format is a short pitch, then questions. Up to three of you present; everyone in the group may
        attend.
      </p>
      <p className="notice">Coming soon: uploading your deck here. For now, bring it to the session.</p>
      <Invitation id={view.id} view={view} />
    </>
  );
}
