"use client";

/** The owner's follow-up on the idea page: answer the desk's question, or "Disagree with this?" (§4.12 day one). */
import { useRouter } from "next/navigation";

import { FollowUp } from "@/app/share/[id]/done/follow-up";

export function FollowUpPanel(props: {
  uuid: string;
  question: { text: string; due: string } | null;
  canDisagree: boolean;
}) {
  const router = useRouter();
  return (
    <FollowUp
      id={props.uuid}
      question={props.question}
      canDisagree={props.canDisagree}
      headingLevel={3}
      onChanged={async () => router.refresh()}
    />
  );
}
