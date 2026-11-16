import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { emptyCanvas } from "@/lib/canvas/model";
import { currentUser } from "@/server/auth/current";
import { canvasConfig, kfinDomains } from "@/server/canvas-config";
import { isOn, switchStates } from "@/server/killswitch";
import { getDraft, SubmissionError } from "@/server/submissions";

import { CanvasForm } from "./canvas-form";

export const metadata: Metadata = { title: "Share an idea" };
export const dynamic = "force-dynamic";

export default async function Draft({ params }: { params: Promise<{ id: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const id = (await params).id;
  let draft;
  try {
    draft = await getDraft(me, id);
  } catch (err) {
    if (err instanceof SubmissionError && err.status === 404) notFound();
    throw err;
  }
  if (draft.stage !== "draft") redirect(`/share/${id}/done`);
  const config = await canvasConfig();
  const states = await switchStates().catch(() => new Map<string, "on" | "off">());
  return (
    <CanvasForm
      id={id}
      mode={draft.mode}
      initial={draft.canvas ?? emptyCanvas(draft.mode)}
      limits={config.canvas}
      rubric={config.canvas_strength}
      kfinDomains={kfinDomains()}
      attachments={draft.attachments}
      attachmentLimits={config.attachments}
      micHint={isOn(states, "capture.mic_hint")}
      voice={isOn(states, "capture.voice")}
    />
  );
}
