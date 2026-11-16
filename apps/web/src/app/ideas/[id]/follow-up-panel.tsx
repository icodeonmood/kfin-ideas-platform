"use client";

/** The owner's follow-up on the idea page: answer the desk's question ("Disagree with this?" is retired, DEC-106). */
import { useRouter } from "next/navigation";

import { FollowUp } from "@/app/share/[id]/done/follow-up";

export function FollowUpPanel(props: { uuid: string; question: { text: string; due: string } | null }) {
  const router = useRouter();
  return (
    <FollowUp
      id={props.uuid}
      question={props.question}
      headingLevel={3}
      onChanged={async () => router.refresh()}
    />
  );
}
