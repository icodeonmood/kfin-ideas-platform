import { redirect } from "next/navigation";

const IDEA_REF = /^IDEA-\d{4}-\d{6}$/;

/** The reviewer's page moved to `/desk/ideas/:id` (S-R2, P-REPO.screens route moves). A link with an idea's
 * reference opens that idea; an old review item number has no idea to point to, so it opens the desk. */
export default async function ReviewItemMoved({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<never> {
  const { id } = await params;
  redirect(IDEA_REF.test(id) ? `/desk/ideas/${id}` : "/desk");
}
