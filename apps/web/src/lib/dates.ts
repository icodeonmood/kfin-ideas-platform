/** Dates on screen, in India time and plain words: "Mon, 23 Nov 2026". */
export function day(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00+05:30` : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });
}

/** A repo history time ("2026-11-08 23:02", India time) in plain words: "Sun, 8 Nov 2026, 11:02 pm". */
export function historyTime(when: string): string {
  const m = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})$/.exec(when);
  if (!m) return when;
  const d = new Date(`${m[1]}T${m[2]}:00+05:30`);
  return d.toLocaleString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}
