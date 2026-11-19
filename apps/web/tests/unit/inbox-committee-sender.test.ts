// @vitest-environment jsdom
/**
 * DEC-113 (BLD-A231), C-INBOX-READER on S-H5 and `/inbox/:itemId`: a sharer never sees a committee member's name. The
 * worker sends the Ones Committee's reversal to the sharer and the crew, and a member's comment or mention with
 * `as_committee`, as "The Ones Committee" with no id and no initials. The reader draws it with no face, no initials
 * and not the desk's 1% mark, in the row (the place kept, empty) and the open item's header (no avatar at all), on
 * desktop and phone alike. The review desk and the committee still read "{name} from the Ones Committee" with the
 * member's initials (L-INBOX.kinds "Sender display"). J-COMMITTEE, J-TRACK. Synthetic people only.
 */
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { Avatar, drawsMark, drawsNoFace, InboxReader, rowName, senderOf } from "@/app/inbox/inbox-reader";
import { ONES_COMMITTEE, ONES_COMMITTEE_START } from "@/lib/review-desk";
import type { InboxEntry, InboxList } from "@/server/inbox";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined }),
  useSearchParams: () => new URLSearchParams(""),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

const AT = new Date().toISOString();
const AS_ONE = { id: "", name: "The Ones Committee", first_name: "The Ones Committee", initials: "" };
const ROHAN = {
  id: "u-rohan",
  name: "Rohan Mehta",
  first_name: "Rohan",
  initials: "RM",
  role_label: "from the Ones Committee",
};

function entry(
  id: string,
  kind: InboxEntry["kind"],
  from: InboxEntry["from"],
  sender: string,
  line: string,
): InboxEntry {
  return {
    id,
    kind,
    from,
    idea: {
      id: "IDEA-2026-000912",
      title: "Investors call to ask why a redemption was rejected",
      status: "not_now",
    },
    line,
    at: AT,
    unread: true,
    needs_you: false,
    archived: false,
    body: { heading: "Decision reversed", note: "", sender },
    actions: [],
  } as InboxEntry;
}

const REVERSED = entry(
  "i-rev",
  "decision_reversed",
  AS_ONE,
  ONES_COMMITTEE_START,
  "reversed a decision on your idea",
);
const COMMENT = entry("i-com", "comment", AS_ONE, ONES_COMMITTEE_START, "commented on your idea");
const MENTION = entry("i-men", "mention", AS_ONE, ONES_COMMITTEE_START, "mentioned you");
const FOR_THE_REVIEWER = entry(
  "i-rev-desk",
  "decision_reversed",
  ROHAN,
  "Rohan Mehta from the Ones Committee",
  "reversed your decision on this idea",
);

function html(node: ReturnType<typeof createElement>): string {
  const host = document.createElement("div");
  host.innerHTML = renderToString(node);
  return host.innerHTML;
}

describe("DEC-113 C-INBOX-READER: the Ones Committee as one has no face", () => {
  it("the shared words", () => {
    expect([ONES_COMMITTEE, ONES_COMMITTEE_START]).toEqual(["the Ones Committee", "The Ones Committee"]);
  });

  it("L-INBOX.kinds: the reversal, a comment and a mention read The Ones Committee with no face, initials or mark", () => {
    for (const item of [REVERSED, COMMENT, MENTION]) {
      expect(senderOf(item), item.kind).toBe("The Ones Committee");
      expect(drawsMark(item), item.kind).toBe(false);
      expect(drawsNoFace(item), item.kind).toBe(true);
      const av = html(createElement(Avatar, { item, size: "sm" }));
      expect(av, item.kind).toBe('<span class="ibx-av ibx-av-sm none" aria-hidden="true"></span>');
      expect(rowName(item, new Date()), item.kind).toMatch(new RegExp(`^The Ones Committee ${item.line}, `));
    }
  });

  it("J-TRACK S-H5.layout: the row keeps an empty place and the open item's header draws no avatar", () => {
    const items = [REVERSED, COMMENT, MENTION];
    const initial: InboxList = {
      items,
      total: items.length,
      counts: { all: 3, needs_you: 0, unread: 3, archived: 0 },
      unread: 3,
    };
    // The server's desktop layout has the first item open in the reader (S-H5.rules/2); `/inbox/:itemId` opens one
    for (const initialItem of [null, "i-rev", "i-com", "i-men"]) {
      const page = html(createElement(InboxReader, { initial, initialTab: "all", initialItem }));
      expect(page, String(initialItem)).not.toMatch(/Rohan|Mehta|>RM<|>1%</);
      expect(page, String(initialItem)).toContain("The Ones Committee");
      const host = document.createElement("div");
      host.innerHTML = page;
      const rows = Array.from(host.querySelectorAll(".ibx-row .ibx-av"));
      expect(rows.length, String(initialItem)).toBe(items.length);
      for (const av of rows) {
        expect(av.classList.contains("none"), String(initialItem)).toBe(true);
        expect(av.classList.contains("sys"), String(initialItem)).toBe(false);
        expect(av.textContent, String(initialItem)).toBe("");
      }
      const header = host.querySelector(".ibx-from");
      expect(header, String(initialItem)).not.toBeNull();
      expect(header?.classList.contains("noav"), String(initialItem)).toBe(true);
      expect(header?.querySelector(".ibx-av"), String(initialItem)).toBeNull();
      expect(header?.textContent, String(initialItem)).toMatch(/^The Ones Committee /);
    }
  });

  it("L-INBOX.kinds: the review desk and the committee still read the member by name, with initials", () => {
    expect(senderOf(FOR_THE_REVIEWER)).toBe("Rohan Mehta from the Ones Committee");
    expect(drawsNoFace(FOR_THE_REVIEWER)).toBe(false);
    expect(drawsMark(FOR_THE_REVIEWER)).toBe(false);
    expect(html(createElement(Avatar, { item: FOR_THE_REVIEWER, size: "md" }))).toContain(">RM<");
    const initial: InboxList = {
      items: [FOR_THE_REVIEWER],
      total: 1,
      counts: { all: 1, needs_you: 0, unread: 1, archived: 0 },
      unread: 1,
    };
    const host = document.createElement("div");
    host.innerHTML = html(
      createElement(InboxReader, { initial, initialTab: "all", initialItem: "i-rev-desk" }),
    );
    expect(host.querySelector(".ibx-from")?.classList.contains("noav")).toBe(false);
    expect(host.querySelector(".ibx-from .ibx-av")?.textContent).toBe("RM");
  });
});
