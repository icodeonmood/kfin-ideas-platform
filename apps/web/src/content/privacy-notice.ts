/**
 * Privacy notice shown at first sign-in (§6.2). DRAFT for Legal and the DPO: "No launch without it" (§9.1).
 * The version here must equal PRIVACY_NOTICE_VERSION; acceptance is stored against that version, and a new
 * version asks everyone again. Every "to be confirmed" line needs Legal's wording before 16 November.
 */
export const PRIVACY_NOTICE = {
  version: "0.1-draft",
  title: "How 1% Club uses your information",
  draft: true,
  sections: [
    {
      heading: "What we use",
      paragraphs: [
        "Your name, work email, employee ID, line of business, role and work location, from KFintech's HR directory.",
        "What you share here: your ideas, comments, files and choices such as teaming up with colleagues.",
      ],
    },
    {
      heading: "Why we use it",
      paragraphs: [
        "To run the ideas programme: to review ideas, find colleagues working on the same thing, keep you informed, and recognise contributions.",
        "Outside the app, your ideas carry a contributor code instead of your name. Your name is shown on the public wall only if you agree.",
        "Before any AI assistant reads your idea, names and personal details are replaced with labels. The assistant never sees them.",
        "Your contribution history is not used in performance appraisal unless HR policy says so. (To be confirmed by HR.)",
      ],
    },
    {
      heading: "Never share",
      paragraphs: [
        "Investor or customer personal data, such as PAN, Aadhaar, folio or account numbers, phone numbers or addresses. The platform blocks them, but please don't type them.",
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
