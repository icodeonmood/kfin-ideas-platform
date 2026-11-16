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
  | "learning.jobs"
  | "ember.send"
  | "solutions.publish"
  | "committee.flow"
  | "appeals.filing"
  | "capture.mic_hint"
  | "capture.voice"
  | "speech.hosted";

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
  // Voice notes (DEC-096): new recordings stop with capture.voice. Reading and deleting one already made carry on.
  { methods: ["POST"], pattern: /^\/api\/submissions\/[^/]+\/voice\/?$/, switches: ["capture.voice"] },
  { methods: WRITE, pattern: /^\/api\/submissions(?:\/.*)?$/, switches: ["submissions"] },
  { methods: ["PUT"], pattern: /^\/api\/ideas\/[^/]+\/canvas\/?$/, switches: ["submissions"] },
  {
    methods: ["POST"],
    pattern: /^\/api\/ideas\/[^/]+\/(?:plus-one|answer)\/?$/,
    switches: ["submissions"],
  },
  {
    methods: ["GET"],
    pattern: /^\/api\/attachments\/(?!.*\/status\/?$)[^/]+\/?$/,
    switches: ["attachments.open"],
  },
  { methods: ["GET"], pattern: /^\/api\/wall\/?$/, switches: ["wall.public"] },
  { methods: ["GET"], pattern: /^\/api\/ones(?:\/constellation)?\/?$/, switches: ["ones.public"] },
  { methods: ["GET"], pattern: /^\/api\/submissions\/[^/]+\/scan-events\/?$/, switches: ["scan.live"] },
  // The org-wide announcement names Ones: it waits while they are off the wall (Ones review).
  { methods: ["POST"], pattern: /^\/api\/ones\/announce\/?$/, switches: ["ones.public"] },
  // Running a learning loop by hand stops with the scheduled ones (§5); the worker refuses it too.
  { methods: ["POST"], pattern: /^\/api\/learning\/run\/?$/, switches: ["learning.jobs"] },
  // The Ember names Ones: sending waits while it is paused or while the Ones are off the wall (BLD-128).
  { methods: ["POST"], pattern: /^\/api\/ember\/[^/]+\/send\/?$/, switches: ["ember.send", "ones.public"] },
  // Evidence files on deliveries use the same pipeline and switches as research files (BLD-131).
  { methods: ["POST"], pattern: /^\/api\/delivery\/[^/]+\/evidence\/?$/, switches: ["attachments.upload"] },
  {
    methods: ["GET"],
    pattern: /^\/api\/delivery\/[^/]+\/evidence\/[^/]+\/?$/,
    switches: ["attachments.open"],
  },
  // The assistant drafting a handover pack stops with the assistant; its own `agent.handover-draft` switch is
  // checked by the gateway, and the page says so (BLD-138).
  { methods: ["POST"], pattern: /^\/api\/delivery\/[^/]+\/pack-draft\/?$/, switches: ["ai.all"] },
  // Approving a write-up publishes it to everyone's "Already running" matches (BLD-133).
  {
    methods: ["POST"],
    pattern: /^\/api\/delivery\/[^/]+\/writeup\/approve\/?$/,
    switches: ["solutions.publish"],
  },
  {
    methods: ["POST"],
    pattern:
      /^\/api\/(?:committee\/(?:cycles|rounds\/[^/]+\/action|presentations\/[^/]+\/action)|presentations\/[^/]+\/action|admin\/conflicts)\/?$/,
    switches: ["committee.flow"],
  },
];

/**
 * Plain words for the banner when a switch is off. Wording to be confirmed by HR with the message templates.
 * The one source for these notices: screens that explain a paused feature import them, never copy them (BLD-157).
 */
export const BANNERS: Record<SwitchName, string> = {
  "ai.all": "The assistant is taking a break. Your idea is saved and we will check it shortly.",
  submissions:
    "Sharing and editing ideas is paused for a short while. You can still browse and track your ideas.",
  "attachments.upload":
    "Adding research files is paused for now. You can still share your idea and add links.",
  "attachments.open": "Research files can't be opened right now. Please try again later.",
  "matching.show": "We will show you colleagues with similar ideas a little later.",
  "comms.email": "Emails are paused for now. Your messages are on your Messages page.",
  "wall.public": "The ideas wall is resting for now. Your own ideas are in My ideas.",
  "ones.public": "The Ones are resting from the wall for a little while.",
  "clusters.batch": "Weekly grouping of similar ideas is paused for now.",
  "scan.live": "Live progress is off. This page checks for updates every few seconds instead.",
  "learning.jobs": "Learning reports and proposals are paused for now. Nothing changes without a person.",
  "ember.send": "Sending The Ember is paused for now.",
  "solutions.publish":
    "Publishing new write-ups is paused for now. Your write-up is saved and can be approved later.",
  "committee.flow": "The committee's reviews and decisions are paused for now.",
  "appeals.filing": "Appeals are paused for a short while. Please try again later.",
  // DEC-096: off only hides the hint under the quick capture box; nothing else changes, so no banner shows it.
  "capture.mic_hint": "The tip about your phone keyboard's mic is hidden for now.",
  "capture.voice": "Voice notes are coming soon.",
  // Employees never see a vendor's name (DEC-096).
  "speech.hosted": "Clearer voice notes, in more Indian languages, are coming soon.",
};

/** Why an action waits while a feature is paused, said after that feature's notice (BLD-157). */
export const BECAUSE = {
  emberWaitsForOnes: "The Ember names them, so it can't go out until they are back.",
  announcementWaitsForOnes:
    "The announcement names them, so it waits. Show the Ones on the wall again first (Admin page).",
} as const;

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
  /^\/api\/ones\/(?:proposals(?:\/[^/]+\/(?:decide|carry-out|withdraw|messages|invites))?|[^/]+\/(?:measures|awards)|screen-mode)\/?$/,
  // A One's own record: their number, brief, glow-up and Showcase brief change nothing about ideas.
  /^\/api\/me\/one\/(?:number|brief|showcase|glow-up\/[^/]+\/seen)\/?$/,
  // Delivery (§4.8 to §4.11) is the work itself: owners, sponsors and PMs keep recording it whatever is paused,
  // like the review desk. Text checks inside these calls answer 503 on their own when the assistant is off.
  /^\/api\/delivery(?:\/[^/]+\/(?:pack|submit|approve|send-back|link|phase|milestones(?:\/[^/]+)?|complete|approve-completion|checkin|evidence\/[^/]+|writeup(?:\/(?:submit|send-back))?|measurements\/[^/]+(?:\/(?:confirm|finance))?))?\/?$/,
  /^\/api\/lenses\/rebuild\/?$/, // counts only, from the database; §7.6 has no lens switch
  // Drafting The Ember, writing the chair's note and the chair approving it send nothing; sending is behind
  // ember.send (BLD-128, BLD-134).
  /^\/api\/ember\/(?:drafts|[^/]+\/(?:note|ready))\/?$/,
  /^\/api\/learning\/proposals\/[^/]+\/decide\/?$/, // a person recording a decision on a proposal already made
  /^\/api\/learning\/role-themes\/[^/]+\/decide\/?$/, // the same for a role's friction themes (BLD-139)
  /^\/api\/learning\/committee\/proposals\/[^/]+\/decide\/?$/, // the core committee deciding one (BLD-149, BLD-150)
  // An admin writing an approved term or tag into the company repo (BLD-136): a person's own console step on the
  // admin page, not employee-facing; the text checks answer 503 on their own when the assistant is off.
  /^\/api\/learning\/proposals\/[^/]+\/publish\/?$/,
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
