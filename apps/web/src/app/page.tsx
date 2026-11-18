import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";

import { Landing } from "./landing";

export const dynamic = "force-dynamic";

/**
 * `/`: signed out it is S-01 Landing (BLD-A172); anyone signed in is on Home, which is S-03 at `/home`
 * (P-ROUTES.screens, BLD-C143). S-03 supersedes the old home page (DEC-099).
 */
export default async function Root() {
  const me = await currentUser();
  if (!me) return <Landing />;
  redirect("/home");
}
