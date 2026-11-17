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
  | "comms.teams"
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
  | "speech.hosted"
  | "files.blackout"
  | "desk.listen";

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
  // Drafts by voice through Sarvam (DEC-108, BLD-C112): starting, sending and ending a note need voice notes, the
  // hosted speech route and sharing. Reading a finished note's words carries on.
  {
    methods: ["POST"],
    pattern: /^\/api\/drafts\/[^/]+\/voice\/(?:start|chunk|end)\/?$/,
    switches: ["capture.voice", "speech.hosted", "submissions"],
  },
  { methods: WRITE, pattern: /^\/api\/submissions(?:\/.*)?$/, switches: ["submissions"] },
  // An Inbox item's op (a team-up request's Decline, Team up only or Merge it) changes ideas and crews: it pauses
  // with sharing (S-H5, notify.ops).
  { methods: ["POST"], pattern: /^\/api\/inbox\/[^/]+\/actions\/[^/]+\/?$/, switches: ["submissions"] },
  // "Show it" puts a hidden detail back in what others read: it waits while sharing is paused (L-HIDE.rules/6).
  { methods: ["POST"], pattern: /^\/api\/drafts\/[^/]+\/hidden\/[^/]+\/show\/?$/, switches: ["submissions"] },
  // The live draft (L-DRAFT): saving pauses with sharing. It never needs `ai.all`: with the assistant off the parts
  // are filled by hand (DEC-105).
  { methods: WRITE, pattern: /^\/api\/drafts(?:\/.*)?$/, switches: ["submissions"] },
  { methods: ["PUT"], pattern: /^\/api\/ideas\/[^/]+\/canvas\/?$/, switches: ["submissions"] },
  {
    methods: ["POST"],
    pattern: /^\/api\/ideas\/[^/]+\/answer\/?$/,
    switches: ["submissions"],
  },
  // Restoring a withdrawn idea shares it again (L-SUBMIT.withdraw/3); withdrawing only takes it back, so it stays open.
  { methods: ["POST"], pattern: /^\/api\/ideas\/[^/]+\/restore\/?$/, switches: ["submissions"] },
  // An idea's conversation (lane F; L-CONVO, BLD-F058): writing or removing a message pauses with sharing, like
  // answering the desk above. Reading it stays open, so the conversation still reads in read-only mode.
  {
    methods: WRITE,
    pattern: /^\/api\/ideas\/[^/]+\/conversation\/messages(?:\/[^/]+)?\/?$/,
    switches: ["submissions"],
  },
  {
    methods: ["GET"],
    pattern: /^\/api\/attachments\/(?!.*\/status\/?$)[^/]+\/?$/,
    switches: ["attachments.open"],
  },
  { methods: ["GET"], pattern: /^\/api\/wall\/?$/, switches: ["wall.public"] },
  // The office screen's Ones (S-OFFICE) rest with the rest of the public Ones.
  {
    methods: ["GET"],
    pattern: /^\/api\/(?:ones(?:\/constellation)?|display\/office)\/?$/,
    switches: ["ones.public"],
  },
  // The 1% Club's Wall and the Ones' posts (lane E, A-API.wall): the worker checks the same switches again.
  {
    methods: ["GET"],
    pattern: /^\/api\/wall\/(?:kindling|just-in|impact|ember)\/?$/,
    switches: ["wall.public"],
  },
  { methods: ["GET"], pattern: /^\/api\/wall\/ones\/?$/, switches: ["wall.public", "ones.public"] },
  {
    methods: ["GET", "PUT"],
    pattern: /^\/api\/ones\/posts(?:\/[^/]+\/like)?\/?$/,
    switches: ["ones.public"],
  },
  { methods: ["GET"], pattern: /^\/api\/submissions\/[^/]+\/scan-events\/?$/, switches: ["scan.live"] },
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
  // Listen's audio and chapters through Sarvam (DEC-108, BLD-C114): lane B's player switch and hosted speech.
  {
    methods: ["GET"],
    pattern: /^\/api\/ideas\/[^/]+\/listen(?:\/chapters)?\/?$/,
    switches: ["desk.listen", "speech.hosted"],
  },
  // The Ones Committee's window (L-COMMITTEE): extending and reversing pause with the committee's flow.
  {
    methods: ["POST"],
    pattern: /^\/api\/committee\/windows\/[^/]+\/(?:extend|reverse)\/?$/,
    switches: ["committee.flow"],
  },
  // The sharer answering the review desk (S-R3) is editing their idea: read-only mode (§7.6) pauses it too.
  { methods: ["POST"], pattern: /^\/api\/question-sets\/[^/]+\/send\/?$/, switches: ["submissions"] },
  { methods: ["PUT"], pattern: /^\/api\/questions\/[^/]+\/answer\/?$/, switches: ["submissions"] },
  // Listen (C-LISTEN): first in Thursday's drop order, so it can be switched off on its own (SHIP_PLAN §4).
  // Lane C's hosted audio for the same player (DEC-108), GET /api/ideas/:id/listen and its /chapters, has its rule
  // in lane C's c/sarvam (desk.listen and speech.hosted), so there is one rule for those paths (BLD-B245).
  { methods: ["GET"], pattern: /^\/api\/desk\/ideas\/[^/]+\/listen\/?$/, switches: ["desk.listen"] },
  // Team up, a draft's merge request and crews (lane F; L-TEAMUP, L-MERGE.request, BLD-F019) pause with sharing:
  // each one writes a note or a reason, changes who is on a crew, or merges an idea. Reads stay open, so a
  // request already sent still reads "Waiting for Ravi".
  { methods: ["POST"], pattern: /^\/api\/ideas\/[^/]+\/team-up\/?$/, switches: ["submissions"] },
  { methods: WRITE, pattern: /^\/api\/team-up\/[^/]+(?:\/answer)?\/?$/, switches: ["submissions"] },
  { methods: WRITE, pattern: /^\/api\/drafts\/[^/]+\/merge-request\/?$/, switches: ["submissions"] },
  { methods: WRITE, pattern: /^\/api\/ideas\/[^/]+\/crew\/[^/]+\/?$/, switches: ["submissions"] },
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
  "comms.email": "Emails are paused for now. Your messages are in your Inbox.",
  // DEC-105: off until IT approves the Teams app. Not a banner: everything still reaches the Inbox and email.
  "comms.teams": "Teams messages are coming soon. Everything still reaches your Inbox and your email.",
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
  // Employees never see a vendor's name (DEC-096). Since DEC-108 the hosted route is how voice works, so off pauses it.
  "speech.hosted": "Voice notes are paused for a short while. You can type instead.",
  // DEC-107: until black-out passes review, a file with a detail found opens only for its sharer and the desk.
  "files.blackout":
    "Hiding details inside a file is coming soon. The review desk will look at the file with you.",
  // The review desk's player (C-LISTEN, BLD-B230). Wording to be confirmed by HR.
  "desk.listen": "Listening to an idea is paused for now. You can still read it on the page.",
};

/** Why an action waits while a feature is paused, said after that feature's notice (BLD-157). */
export const BECAUSE = {
  emberWaitsForOnes: "The Ember names them, so it can't go out until they are back.",
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
  // Reading, marking unread, archiving and "Mark all read" change only the person's own Inbox, nothing about ideas;
  // they work in read-only mode (L-INBOX).
  /^\/api\/inbox\/(?:read-all|[^/]+\/(?:read|unread|archive))\/?$/,
  /^\/api\/me\/comms-prefs\/?$/, // a person's own preferences (name on the wall) change nothing about ideas
  /^\/api\/me\/refer-as\/?$/, // how a person wants to be referred to (BLD-C111) changes nothing about ideas
  /^\/api\/me\/app-news\/?$/, // "Tell me when it's out" for the app (S-H3, L-NOTIFY/7): a person's own choice, no idea
  /^\/api\/review\/items\/[^/]+\/(?:action|veto)\/?$/, // the desk keeps clearing the queue while submissions are paused; §7.6 has no review switch
  // The Ones console's calls keep working whatever is paused: it is the committee's own record (DEC-040). Text
  // checks inside these calls answer 503 on their own when the assistant is off. The console page, awards and the
  // announcement are retired (DEC-106); proposals stay until lane A's admin path replaces them.
  /^\/api\/ones\/(?:proposals(?:\/[^/]+\/(?:decide|carry-out|withdraw|messages|invites))?|[^/]+\/measures|screen-mode)\/?$/,
  // A One's own record: their number, brief, glow-up and Showcase brief change nothing about ideas.
  /^\/api\/me\/one\/(?:number|brief|showcase|glow-up\/[^/]+\/seen)\/?$/,
  // The same on the 1% Club's dashboard (lane E, S-ONE), and a person's own Profile switches (S-H6): their own
  // record, nothing about ideas. A brief's text checks run inside the call whatever is paused (V-FIELDS.one/4).
  /^\/api\/one\/(?:number|brief|glow-up\/[^/]+\/seen)\/?$/,
  /^\/api\/me\/settings\/?$/,
  // Delivery (§4.8 to §4.11) is the work itself: owners, sponsors and PMs keep recording it whatever is paused,
  // like the review desk. Text checks inside these calls answer 503 on their own when the assistant is off.
  /^\/api\/delivery(?:\/[^/]+\/(?:pack|submit|approve|send-back|link|phase|milestones(?:\/[^/]+)?|complete|approve-completion|checkin|evidence\/[^/]+|writeup(?:\/(?:submit|send-back))?|measurements\/[^/]+(?:\/(?:confirm|finance))?))?\/?$/,
  // Drafting The Ember, writing the chair's note and the chair approving it send nothing; sending is behind
  // ember.send (BLD-128, BLD-134).
  /^\/api\/ember\/(?:drafts|[^/]+\/(?:note|ready))\/?$/,
  // L-HIDE (BLD-C060): hiding only ever protects someone, so the desk's "Hide this" and the sharer's "Hide it" work
  // whatever is paused.
  /^\/api\/desk\/ideas\/[^/]+\/hide\/?$/,
  /^\/api\/drafts\/[^/]+\/hidden\/[^/]+\/hide\/?$/,
  // The review desk (S-R2, lane B): opening, revising worth, deciding, merging and asking keep working while
  // submissions are paused, as the desk always has (line above for /api/review/items); §7.6 has no review switch.
  /^\/api\/desk\/ideas\/[^/]+\/(?:open|worth|decision|merge|question-sets)\/?$/,
  // "Give 2 more days" and "Send a reminder" only move a deadline or nudge the sharer; they change no idea.
  /^\/api\/question-sets\/[^/]+\/(?:extend|remind)\/?$/,
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
