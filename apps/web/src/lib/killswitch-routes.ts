/**
 * Which kill switches guard which API routes (§7.6, §8). Pure data so it is easy to test and review.
 * A request is refused with 503 when any switch it needs is "off". GET routes that only read stay open,
 * except the ones whose whole purpose a switch removes (opening files, the public wall).
 */

export type SwitchName =
  | "ai.all"
  | "submissions"
  | "attachments.upload"
  | "attachments.open"
  | "matching.show"
  | "comms.email"
  | "wall.public"
  | "ones.public"
  | "clusters.batch"
  | "scan.live"
  | "committee.flow";

interface Rule {
  methods: readonly string[];
  pattern: RegExp;
  switches: readonly SwitchName[];
}

const WRITE = ["POST", "PUT", "PATCH", "DELETE"] as const;

export const ROUTE_RULES: readonly Rule[] = [
  {
    methods: ["POST"],
    pattern: /^\/api\/submissions\/[^/]+\/attachments\/?$/,
    switches: ["attachments.upload"],
  },
  { methods: WRITE, pattern: /^\/api\/submissions(?:\/.*)?$/, switches: ["submissions"] },
  { methods: ["PUT"], pattern: /^\/api\/ideas\/[^/]+\/canvas\/?$/, switches: ["submissions"] },
  {
    methods: ["POST"],
    pattern: /^\/api\/ideas\/[^/]+\/(?:plus-one|answer|disagree)\/?$/,
    switches: ["submissions"],
  },
  { methods: ["POST"], pattern: /^\/api\/clusters\/[^/]+\/join\/?$/, switches: ["submissions"] },
  {
    methods: ["GET"],
    pattern: /^\/api\/attachments\/(?!.*\/status\/?$)[^/]+\/?$/,
    switches: ["attachments.open"],
  },
  { methods: ["GET"], pattern: /^\/api\/wall\/?$/, switches: ["wall.public"] },
  { methods: ["GET"], pattern: /^\/api\/ones(?:\/constellation)?\/?$/, switches: ["ones.public"] },
  { methods: ["POST"], pattern: /^\/api\/review\/cluster-runs\/?$/, switches: ["clusters.batch"] },
  { methods: ["GET"], pattern: /^\/api\/submissions\/[^/]+\/scan-events\/?$/, switches: ["scan.live"] },
  {
    methods: ["POST"],
    pattern:
      /^\/api\/(?:committee\/(?:cycles|rounds\/[^/]+\/action|presentations\/[^/]+\/action)|presentations\/[^/]+\/action|review\/qualify\/[^/]+)\/?$/,
    switches: ["committee.flow"],
  },
];

/** Plain words for the banner when a switch is off. Wording to be confirmed by HR with the message templates. */
export const BANNERS: Record<SwitchName, string> = {
  "ai.all": "The assistant is taking a break. Your idea is saved and we will check it shortly.",
  submissions:
    "Sharing and editing ideas is paused for a short while. You can still browse and track your ideas.",
  "attachments.upload":
    "Adding research files is paused for now. You can still share your idea and add links.",
  "attachments.open": "Research files can't be opened right now. Please try again later.",
  "matching.show": "We will show you colleagues with similar ideas a little later.",
  "comms.email": "Emails are paused for now. Your messages are in your in-app inbox.",
  "wall.public": "The ideas wall is resting for now. Your own ideas are in My ideas.",
  "ones.public": "The Ones are resting from the wall for a little while.",
  "clusters.batch": "Weekly grouping of similar ideas is switched off for now.",
  "scan.live": "Live progress is off. This page checks for updates every few seconds instead.",
  "committee.flow": "The committee's reviews and decisions are switched off for now.",
};

/**
 * Write routes that deliberately need no kill switch (each one reviewed). A unit test fails if a route
 * file exports POST, PUT, PATCH or DELETE and its path is neither guarded above nor listed here, so a new
 * write route cannot ship ungated by accident.
 */
export const UNGUARDED_WRITES: readonly RegExp[] = [
  /^\/api\/me\/privacy-notice\/?$/, // accepting the notice must work in read-only mode, or nobody could browse
  /^\/api\/admin\/kill-switches\/?$/, // admins must be able to switch features back on
  /^\/api\/admin\/roles(?:\/[^/]+)?\/?$/, // granting a reviewer must not depend on submissions being open
  /^\/api\/inbox\/[^/]+\/read\/?$/, // marking a message read changes nothing about ideas; works in read-only mode
  /^\/api\/me\/comms-prefs\/?$/, // a person's own preferences (name on the wall) change nothing about ideas
  /^\/api\/review\/items\/[^/]+\/(?:action|veto)\/?$/, // the desk keeps clearing the queue while submissions are paused; §7.6 has no review switch
  // The Ones console keeps working whatever is paused: it is the committee's own record (DEC-040). Text checks
  // inside these calls answer 503 on their own when the assistant is off.
  /^\/api\/ones\/(?:proposals(?:\/[^/]+\/(?:decide|carry-out|withdraw|messages|invites))?|[^/]+\/(?:measures|awards)|screen-mode|announce)\/?$/,
  // A One's own record: their number, brief, glow-up and Showcase brief change nothing about ideas.
  /^\/api\/me\/one\/(?:number|brief|showcase|glow-up\/[^/]+\/seen)\/?$/,
  /^\/api\/review\/cluster-proposals\/[^/]+\/action\/?$/, // deciding proposals already made needs no switch; new runs are behind clusters.batch
];

export function switchesFor(method: string, pathname: string): SwitchName[] {
  // Next.js answers HEAD by running the GET handler, so HEAD must meet the same gates as GET.
  const m = method.toUpperCase() === "HEAD" ? "GET" : method.toUpperCase();
  const needed = new Set<SwitchName>();
  for (const rule of ROUTE_RULES) {
    if (rule.methods.includes(m) && rule.pattern.test(pathname)) {
      rule.switches.forEach((s) => needed.add(s));
    }
  }
  return [...needed];
}
