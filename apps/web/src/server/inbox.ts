/** The in-app inbox (§3.7). The worker renders each message for the person viewing it. */
import type { CurrentUser } from "./auth/current";
import { workerFetch } from "./worker";

export type Message = { id: number; subject: string; body: string; at: string; read: boolean };

export async function messagesFor(me: CurrentUser): Promise<Message[]> {
  const res = await workerFetch(`/internal/inbox/${encodeURIComponent(me.id)}`);
  if (!res.ok) throw new Error(`inbox ${res.status}`);
  return ((await res.json()) as { messages: Message[] }).messages;
}

export async function markRead(me: CurrentUser, id: string): Promise<boolean> {
  if (!/^[0-9]{1,18}$/.test(id)) return false;
  const res = await workerFetch(`/internal/inbox/${encodeURIComponent(me.id)}/${id}/read`, {
    method: "POST",
  });
  return res.ok;
}
