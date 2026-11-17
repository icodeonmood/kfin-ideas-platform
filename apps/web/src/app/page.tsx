import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

/**
 * `/`: Landing (S-01) is for people who are signed out, and the proxy sends them to sign in first; anyone signed in
 * is on Home, which is S-03 at `/home` (P-ROUTES.screens, BLD-C143). S-03 supersedes the old home page (DEC-099).
 */
export default function Root() {
  redirect("/home");
}
