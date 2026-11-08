import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { currentUser } from "@/server/auth/current";
import { messagesFor } from "@/server/inbox";

import { MessageList } from "./message-list";

export const metadata: Metadata = { title: "Messages" };
export const dynamic = "force-dynamic";

export default async function Inbox() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  const messages = await messagesFor(me).catch(() => null);
  return (
    <>
      <h1>Messages</h1>
      {messages === null ? (
        <p className="notice">We can&apos;t load your messages just now. Please try again in a minute.</p>
      ) : messages.length ? (
        <MessageList initial={messages} />
      ) : (
        <p>No messages yet. When something happens to your ideas, you will hear about it here.</p>
      )}
    </>
  );
}
