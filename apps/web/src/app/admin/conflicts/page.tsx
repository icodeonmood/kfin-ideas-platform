import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { conflictFlags } from "@/server/committee";

import { Conflicts, type Flag } from "./conflicts";

export const metadata: Metadata = { title: "Conflict flags" };
export const dynamic = "force-dynamic";

export default async function ConflictFlags() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const { flags } = (await conflictFlags(me)) as { flags: Flag[] };
  return (
    <>
      <p>
        <Link href="/admin">Back to admin</Link>
      </p>
      <h1>Conflict flags</h1>
      <p>
        A committee member is flagged when someone they manage shared or joined an idea in a group under
        review. They can step aside, or you can clear the flag with a reason. Colleagues whose own idea is in
        the group always step aside, so their flags are not listed here.
      </p>
      <Conflicts initial={flags} />
    </>
  );
}
