"use client";

/** Messages as plain text: template Markdown is shown as written, never interpreted as HTML. */
import { useState } from "react";

import type { Message } from "@/server/inbox";

function plain(body: string): string {
  // Light tidy-up of the templates' Markdown: links become "text (url)", bold markers go.
  return body.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)").replace(/\*\*/g, "");
}

export function MessageList({ initial }: { initial: Message[] }) {
  const [messages, setMessages] = useState(initial);
  const [open, setOpen] = useState<number | null>(null);

  async function toggle(m: Message) {
    setOpen(open === m.id ? null : m.id);
    if (!m.read) {
      const res = await fetch(`/api/inbox/${m.id}/read`, { method: "POST" }).catch(() => null);
      if (res?.ok) setMessages((all) => all.map((x) => (x.id === m.id ? { ...x, read: true } : x)));
    }
  }

  return (
    <ul className="inbox">
      {messages.map((m) => (
        <li key={m.id} className={m.read ? "read" : "unread"}>
          <h2 className="inbox-subject">
            <button
              type="button"
              className="link-button"
              aria-expanded={open === m.id}
              aria-controls={`msg-${m.id}`}
              onClick={() => void toggle(m)}
            >
              {m.read ? "" : <span className="visually-hidden">New: </span>}
              {m.subject}
            </button>
          </h2>
          <p className="muted">
            {new Date(m.at).toLocaleString("en-IN", {
              dateStyle: "medium",
              timeStyle: "short",
              timeZone: "Asia/Kolkata",
            })}
          </p>
          {open === m.id ? (
            <div id={`msg-${m.id}`} className="inbox-body">
              {plain(m.body)
                .split(/\n{2,}/)
                .map((para, i) => (
                  <p key={i}>{para}</p>
                ))}
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
