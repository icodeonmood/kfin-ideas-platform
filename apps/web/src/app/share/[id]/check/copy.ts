/**
 * S-05 "Check it, then send it": the words on the screen, word for word from 1pc-handoff/reference/copy/Review.md
 * (and PhoneReview.md for the phone's own lines), C-SIMGRID, C-FILE, C-HIDDEN, S-05.fix and V-FIELDS.checkit. Lines
 * the server words (sorting, the fix's readiness, the Send rows, merge outcomes) are shown as the API sends them; the
 * templates here are only for what the client composes from a count or a name. Nothing here is invented: a line the
 * pack does not draw is named NOT DRAWN with where it comes from.
 */

export const PARTS = [
  { n: 1, key: "words", label: "Your words" },
  { n: 2, key: "sorting", label: "Sorting" },
  { n: 3, key: "similar", label: "Similar ideas" },
  { n: 4, key: "proof", label: "Proof" },
  { n: 5, key: "fix", label: "Your fix" },
  { n: 6, key: "helpers", label: "Who would help" },
  { n: 7, key: "send", label: "Send it" },
] as const;

export type PartNo = 1 | 2 | 3 | 4 | 5 | 6 | 7;

const NUMBER_WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight"];

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

export const CHECK_COPY = {
  taskTitle: "Share a problem",
  /** The rail's name for a screen reader: the step it lists. */
  rail: "Check it",
  counter: (n: number) => `Check it, part ${n} of 6`,
  sendCounter: "Step 3 of 3",
  back: "Back",
  next: "Next",
  skip: "Skip for now",
  optional: "Optional",
  added: "Added",
  /** The rail's tick, for a screen reader: the task bar's words for a done step (C-TASKBAR). */
  done: ", done",
  retry: "Try again",
  /** A-API's general failure line (src/server/share.ts FAILED). */
  failed: "Something went wrong. Try again.",

  words: {
    rail: "Title, what happens, how often",
    /** "Title, what happens, how often, 2 files" (Review.md, attached=…). */
    railFiles: (n: number) => `Title, what happens, how often, ${plural(n, "file")}`,
    heading: "Is this how you’d put it?",
    line: "This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.",
    title: "Title",
    summary: "What happens",
    often: "How often",
    change: { title: "Change the title", summary: "Change what happens", often: "Change how often" },
    /** The phone boards: "Change" with what it changes read out ("Change title", PhoneReview.md, PhoneEdit.md). */
    changePhone: "Change",
    changeWhat: { title: "title", summary: "what happens", often: "how often" },
    /** V-FIELDS.checkit/1–2. */
    titleNeeded: "Give it a title of a few words.",
    summaryNeeded: "Say what happens, in a sentence or two.",
    attached: "Attached",
    attachedCount: (n: number) => plural(n, "file"),
    changeAttached: "Change the attached files",
    backToWords: "Back to your words",
    forward: "Looks right",
  },

  hidden: {
    label: "Hidden from everyone",
    show: "Show it",
    /** PhoneReview.md, PhoneEdit.md: a row's button on a phone. */
    showPhone: "Not personal? Show it",
    /** C-HIDDEN.list/1–3. */
    ask: "Only show it if it isn’t about a real customer. What is it?",
    note: "We note your reason with the idea.",
    keep: "Keep it hidden",
    shown: (reason: string) => `Shown, because ${reason}.`,
    hide: "Hide it",
    more: (n: number) => `+${n} more`,
  },

  sorting: {
    heading: "Is it sorted right?",
    line: "Sorting decides who reviews it. We suggested these from your words. Confirm them, or change any of them.",
    affects: "Who it affects",
    kind: "What kind it is",
    area: "Area",
    brings: "What it would bring",
    forward: "Confirm sorting",
    /** V-FIELDS.checkit/3: under the sorting card after trying to send unconfirmed. */
    unconfirmed: "Confirm these, or change any of them, before you send.",
  },

  similar: {
    heading: "Has someone raised this already?",
    /** "Two colleagues shared something close while you were writing. …" (drawn for two; the count is a word). */
    line: (n: number) =>
      `${n < NUMBER_WORDS.length ? NUMBER_WORDS[n] : String(n)} ${n === 1 ? "colleague" : "colleagues"} shared something close while you were writing. Team up with them, and bring yours along if you like, or keep yours separate.`,
    /** S-05.similar NOT DRAWN: no matches. */
    none: "Nobody has raised this yet.",
    /** L-SIMILAR.failure: never "none found". */
    couldnt: "Couldn’t check for similar ideas. The review desk will.",
    /** "2 close ideas found" / "8 similar ideas found" (rail). */
    railFound: (n: number) => (n < 3 ? `${plural(n, "close idea")} found` : `${n} similar ideas found`),
    yours: "Yours, not sent yet",
    carryOn: "None of these the same? Just carry on. Yours goes on its own.",
    kept: "Kept separate. The review desk still sees the similar ideas next to yours.",
    showAgain: "Show them again",
    showMore: "Show more",
    preview: "Preview",
    previewOf: (title: string) => `Preview ${title}`,
    teamUp: "Team up",
    teamUpOn: (title: string) => `Team up on ${title}`,
    waiting: (first: string) => `Waiting for ${first}`,
    withdraw: "Withdraw",
    onCrew: "On the crew",
    grid: "Yours and the similar ideas",
    /** L-MERGE.request/4–7 as drawn, for when the merge request comes without its words (lane F sends them). */
    merge: {
      waitingRail: (first: string) => `Waiting on ${first} to merge`,
      waitingLine: (first: string) =>
        `Waiting for ${first} to accept the merge. If ${first} declines, you can send yours on its own.`,
      withdraw: "Withdraw the request",
      acceptedRail: (ref: string) => `Merged into ${ref}`,
      acceptedLine: (first: string, ref: string) =>
        `${first} accepted. Yours is now part of ${ref}, with credit to you. Nothing else to send.`,
      declinedRail: (first: string) => `${first} kept it separate`,
      sendAlone: "Send mine on its own",
      seeMerged: "See the merged idea",
    },
  },

  proof: {
    heading: "Anything that shows it?",
    line: "Optional, but it helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.",
    links: "Links to a report, dashboard or ticket",
    linkInput: "Paste a link, or attach files. Add several links at once with commas.",
    attach: "Attach files",
    addLink: "Add a link",
    dropTitle: "Drop files here, or",
    browse: "browse",
    /** C-FILE.uploader/1, Check it's help line as drawn; the configured one (GET /config uploads) wins. */
    dropHelp: "Screenshots, photos, PDFs or spreadsheets, up to 25 MB each. You can paste a screenshot too.",
    helpsTitle: "What helps most",
    helps: [
      "A screenshot of the SMS or screen",
      "A call log or ticket count that shows how often",
      "A report with the time or money it costs",
    ],
    count: (n: number) => plural(n, "file"),
    checking: "Checking for personal details",
    checked: "Checked",
    failed: "Didn’t upload. Your other files are fine.",
    tooBig: (mb: number) => `Too big. Files can be up to ${mb} MB.`,
    /** C-FILE.row "Personal data found", when the server sends no line of its own. */
    found: "Nobody can open it until it’s hidden.",
    hideForMe: "Hide it for me",
    /** C-FILE.row: "View" on a checked file (it opens in a new tab until C-FILE.view's pop-up is drawn). */
    view: "View",
    viewOf: (name: string) => `View ${name}`,
    remove: "Remove",
    removeOf: (name: string) => `Remove ${name}`,
    notALink: "That doesn’t look like a link. A link looks like intranet.kfintech.com/page.",
    internal: "Internal link",
    external: "External link",
    link: "Link",
  },

  fix: {
    heading: "Got an idea how to solve it?",
    line: "Optional. A fix helps the review desk weigh it, but problems on their own get picked too.",
    rowTitle: "Say how you’d solve it",
    rowLine:
      "A few short questions: how, what it would need and what it’s worth. Only the first one is needed.",
    add: "Add your fix",
    started: "You started a fix. It isn’t included yet.",
    carryOn: "Carry on with your fix",
    change: "Change",
    changeLabel: "Change your fix",
    remove: "Remove",
    removeLabel: "Remove your fix",
    /** Before the server has worded the part (a fix added on another visit): "Included, 5 of 5 ready". */
    included: (n: number) => `Included, ${n} of 5 ready`,
  },

  sheet: {
    title: "Your fix",
    close: "Close, and keep what you wrote",
    intro: "Optional. Answer what you can; nothing here stops you sending.",
    readiness: (n: number) => `${n} of 5 ready for the review desk`,
    /** The server's lines (services/worker/submit/fix.py NEXT_LINE); "worth" is drawn. */
    next: {
      how: "Most useful next: how you’d solve it. One or two sentences is plenty.",
      worth: "Most useful next: a rough size. A range is fine.",
      solved_already: "Most useful next: whether anyone has solved this already.",
      basis: "Most useful next: what that is based on.",
      needs: "Most useful next: what it would need.",
    },
    how: "How would you solve it?",
    howHelp: "One or two sentences is plenty. The only part a fix needs.",
    needs: "What would it need?",
    needsHelp: "People, systems, partners or money. Helps size the effort early.",
    solved: "Has anyone solved this already?",
    solvedOptions: [
      { value: "yes", label: "Yes" },
      { value: "partly", label: "Partly" },
      { value: "no", label: "No" },
      { value: "dont_know", label: "I don’t know" },
    ],
    worth: "What it’s worth, roughly",
    worthHelp:
      "Pick any that apply. A rough monthly figure is enough, and a range is fine, written any way: 2 lakh, 2L or 2,00,000.",
    hours: "Time saved",
    hoursUnit: "Hours a month",
    hoursPlaceholder: "For example, 70 to 150",
    cost: "Cost saved",
    money: "₹ a month",
    moneyPlaceholder: "25,000 or 25k",
    revenue: "New revenue",
    tools: "Less reliance on outside tools",
    basis: "What is that based on?",
    risks: "What could go wrong, including anything regulatory?",
    risksHelp: "Naming risks early builds trust. It never counts against the idea.",
    optional: "Optional",
    cancel: "Cancel",
    submit: "Add my fix",
    /** V-FIELDS.checkit/8–9. */
    howNeeded: "Say how you’d solve it, or close this to send without a fix.",
    worthUnclear: "Write a rough figure or a range, like 70 to 150.",
  },

  helpers: {
    heading: "Who would help?",
    line: "Optional. It shows on Find your crew as “They’re looking for”, so the right colleagues can team up with you.",
    picks: "Who would help",
    own: "Who would help, in your own words",
    ownPlaceholder: "Or say it your way, for example someone who takes these calls at a branch",
    /** V-FIELDS.checkit/10: counter only. */
    counter: (n: number, max: number) => `${n} of ${max}`,
  },

  send: {
    heading: "Ready to send?",
    line: "One last look. You can still change it until the review desk opens it.",
    change: "Change",
    changeOf: (label: string) => `Change ${label.charAt(0).toLowerCase()}${label.slice(1)}`,
    rail: "One last look, then submit",
    unconfirmed: "Confirm the sorting first, or change any of it.",
    goToSorting: "Go to the sorting",
    sendFailed: "Couldn’t send. Your draft is safe. Check your connection, then try again.",
    offline:
      "You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.",
    submit: "Submit",
    sending: "Sending…",
  },

  /** PhoneReview.md: Check it as one scrolling page (S-05.phone). */
  phone: {
    heading: "Check it, then send it",
    line: "Written only from your words. Change anything that isn’t right.",
    words: "Your problem",
    sorting: "Is this sorted right?",
    confirm: "Yes, that’s right",
    similar: "Already raised?",
    similarLine: (n: number) =>
      `${n < NUMBER_WORDS.length ? NUMBER_WORDS[n] : String(n)} ${n === 1 ? "idea looks" : "ideas look"} close to yours. Team up on one, or send yours linked to it so both are decided together. Sending yours on its own is fine too.`,
    proofLine:
      "It helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.",
    fix: "Your fix",
    fixLine: "It helps the review desk weigh it. Skipping it is fine: problems on their own get picked too.",
    /** The three counts under the heading, each a link to its part ("1 detail hidden", "3 sortings", "2 similar
     * ideas"); the plurals are S-05.phone's ("details hidden, sortings, similar ideas"). */
    hiddenCount: (n: number) => (n === 1 ? "detail hidden" : "details hidden"),
    sortingsCount: (n: number) => (n === 1 ? "sorting" : "sortings"),
    similarCount: (n: number) => (n === 1 ? "similar idea" : "similar ideas"),
  },
} as const;
