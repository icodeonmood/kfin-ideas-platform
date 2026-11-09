import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { constellation } from "@/server/ones";

import { Sky } from "./sky";

export const metadata: Metadata = { title: "The Ones, in the sky" };
export const dynamic = "force-dynamic";

/** The office screen (DEC-058, DEC-069, DEC-074): every One's spark, alternating with impact cards. Silent. */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const data = await constellation().catch(() => null);
  return <Sky data={data} />;
}
