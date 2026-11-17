import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import type { ConfigResponse } from "@/lib/contracts";
import { currentUser } from "@/server/auth/current";
import { isKey, publicConfig } from "@/server/share";

import { CheckIt } from "./check-it";

export const metadata: Metadata = { title: "Check it" };
export const dynamic = "force-dynamic";

/**
 * S-05 "Check it, then send it", `/share/:draftId/check` (P-ROUTES). The owner's draft only: the screen reads it
 * through the API, so a draft that is not theirs answers 404 there. The sorting lists, the declaration and the upload
 * limits come with the page (A-API.config); the screen asks for them itself if this read fails.
 */
export default async function CheckPage({ params }: { params: Promise<{ id: string }> }) {
  const id = (await params).id;
  const me = await currentUser();
  if (!me) redirect(`/sign-in?next=${encodeURIComponent(`/share/${id}/check`)}`);
  if (!isKey(id)) notFound();
  const config: ConfigResponse | null = await publicConfig().catch(() => null);
  return <CheckIt draftId={id} config={config} />;
}
