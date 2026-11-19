/**
 * Privacy notice shown at first sign-in (§6.2). DRAFT for Legal and the DPO: "No launch without it" (§9.1).
 * The version here must equal PRIVACY_NOTICE_VERSION (`.env.example`, `scripts/uat/rehearse.sh`); acceptance is
 * stored against that version, and a new version asks everyone again. 0.2-draft (BLD-A232) corrects who sees what
 * (DEC-104, DEC-106), customer details (DEC-103, DEC-107), voice notes (DEC-108) and how suggestions improve (§5,
 * BLD-121); `docs/privacy-notice-0.2.md` lists every changed sentence for Legal and the DPO. The three "to be
 * confirmed" lines wait for the DPO's wording; the commit that adds it sets "0.2" and `draft: false`.
 */
export const PRIVACY_NOTICE = {
  version: "0.2-draft",
  title: "How 1% Club uses your information",
  draft: true,
  sections: [
    {
      heading: "What we use",
      paragraphs: [
        "Your name, work email, employee ID, line of business, role and work location, from KFintech's HR directory.",
        "What you share here: your ideas, voice notes, files, messages in an idea's conversation, and choices such as teaming up with colleagues.",
      ],
    },
    {
      heading: "Why we use it",
      paragraphs: [
        "To run the ideas programme: to review ideas, find colleagues working on the same thing, keep you informed, and recognise contributions.",
        "We store your ideas against a contributor code, and keep the link to your name separately.",
        "Before any AI assistant reads your idea, names and personal details in the text are replaced with labels. The assistant never sees them. A voice recording is the one exception, because a recording can't be masked. See Voice notes below.",
        "Your contribution history is not used in performance appraisal unless HR policy says so. (To be confirmed by HR.)",
      ],
    },
    {
      heading: "Who sees what",
      paragraphs: [
        "Your name shows on your ideas, on crew cards and on your requests to team up. It also shows on the Wall next to your shared ideas, unless you turn that off in Profile.",
        "The review desk and the Ones Committee see your name.",
        "Only you, the review desk and the Ones Committee read your words. Everyone else sees the short summary.",
        "Your crew also sees the idea's checked files and its conversation.",
        "Your points are private to you.",
      ],
    },
    {
      heading: "Never share",
      paragraphs: [
        "Investor or customer personal data, such as PAN, Aadhaar, folio or account numbers, phone numbers or addresses. Don't type them.",
        "If a PAN, Aadhaar, folio, account or phone number or a customer's email address slips in, it is hidden. It is masked before any other person or service sees your text.",
        "The full value is stored encrypted, and only you can see it.",
        "A file that holds a customer detail opens only for you, the review desk and the Ones Committee.",
      ],
    },
    {
      heading: "Voice notes",
      paragraphs: [
        "If you record a voice note, it goes to an Indian speech service to turn it into text. You can check the text before you send it.",
        "The recording goes as you spoke it, because a recording can't be masked.",
        "Text we send to that service for translation or to be read aloud is masked first. Every transcript is masked as it comes back, before any other person or service sees it.",
      ],
    },
    {
      heading: "How your ideas improve the suggestions",
      paragraphs: [
        "When the review desk changes something the assistant suggested, such as the sorting, we keep that change as a worked example for later suggestions. Names and personal details in it are replaced with labels.",
        "We also count how often suggestions are accepted, and look across ideas for new terms and areas. The product team approves or declines every change these point to.",
        "People decide every change. Nothing changes by itself.",
      ],
    },
    {
      heading: "How long we keep it",
      paragraphs: [
        "As long as KFintech's record-retention policy requires. If you leave KFintech, the link between your name and your contributor code is deleted, so your ideas stay but no longer point to you. (Retention period to be confirmed by Legal.)",
      ],
    },
    {
      heading: "Your choices and questions",
      paragraphs: [
        "You can see and download everything you have shared from My ideas.",
        "For questions or complaints under KFintech's data protection policy, contact the Data Protection Officer. (Contact details to be confirmed by Legal.)",
      ],
    },
  ],
} as const;
