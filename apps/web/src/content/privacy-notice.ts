/**
 * Privacy notice shown at first sign-in (§6.2): "No launch without it" (§9.1).
 * The version here must equal PRIVACY_NOTICE_VERSION (`.env.example`, `scripts/uat/rehearse.sh`, and every server's
 * app env file, which `scripts/uat/deploy.sh` checks); acceptance is stored against that version, and a new version
 * asks everyone again. 0.2-draft (BLD-A232) corrected who sees what (DEC-104, DEC-106), customer details (DEC-103,
 * DEC-107, L-HIDE.rules/6-7), voice notes and listening (DEC-108) and the pronoun from Profile (DEC-108 (3)),
 * with the product lead's calls of 19 Nov on review B3, B5 and B6. 0.2 (BLD-A233) is final: the appraisal,
 * retention and contact lines are the product lead's, provisionally approved; HR, Legal and the DPO confirm later.
 * `docs/privacy-notice-0.2.md` lists every changed sentence for Legal and the DPO.
 */
export const PRIVACY_NOTICE = {
  version: "0.2",
  title: "How 1% Club uses your information",
  draft: false,
  sections: [
    {
      heading: "What we use",
      paragraphs: [
        "Your name, work email, employee ID, line of business, role and work location, from KFintech's HR directory.",
        "What you share here: your ideas, voice notes, files, messages in an idea's conversation, and choices such as teaming up with colleagues.",
        "How you'd like us to refer to you, if you choose to tell us in Profile.",
      ],
    },
    {
      heading: "Why we use it",
      paragraphs: [
        "To run the ideas programme: to review ideas, find colleagues working on the same thing, keep you informed, and recognise contributions.",
        "Inside 1% Club, your ideas are stored under a contributor code, and the link from that code to you is kept in a separate table.",
        "Before the AI assistant reads your idea, our checks look for names and personal details in the text and replace them with labels.",
        "Sharing here is voluntary. What you share is never used against you, and it is not used in your performance appraisal.",
      ],
    },
    {
      heading: "Who sees what",
      paragraphs: [
        "Your name shows on your ideas, on crew cards and on your requests to team up. It also shows on the Wall next to your shared ideas, unless you turn that off in Profile.",
        "The review desk and the Ones Committee see your name.",
        "Only you, the review desk and the Ones Committee read your words. Everyone else sees the short summary.",
        "Your crew also sees the idea's checked files, its conversation, the review desk's questions and your answers, and the decision with its reason. A file in which our checks find a customer detail is the exception (see Never share). Once a build team is chosen, it sees the conversation too, and a colleague you mention in a message sees that message.",
        "Your points are private to you.",
      ],
    },
    {
      heading: "Never share",
      paragraphs: [
        "Investor or customer personal data, such as PAN, Aadhaar, folio or account numbers, phone numbers or addresses. Don't type or say them.",
        "If you include a customer's PAN, Aadhaar, folio, account or phone number, or their email address, our checks look for it and hide it before any other person or service sees your text. The review desk can hide one the checks missed.",
        "The full detail is stored encrypted, and only you can see it. If it isn't a customer's detail, such as a scheme code, you can choose Show it and give a reason, unless the review desk hid it. It is then no longer hidden, and the review desk sees that you showed it and why.",
        "A file in which our checks find a customer detail is not hidden. It opens only for you, the review desk and the Ones Committee, and they see it as it is.",
      ],
    },
    {
      heading: "Voice notes and listening",
      paragraphs: [
        "If you record a voice note, it goes to an Indian speech service to turn it into text. You can check the text before you send it.",
        "The recording goes as you spoke it, because a recording can't be hidden. So don't say a customer's details in a voice note.",
        "If you chose 'she' or 'he' in Profile, that goes to the service with your voice note, so its English copy refers to you correctly.",
        "Before text goes to that service, to make the English copy or to be read aloud, our checks look for customers' details in it and hide what they find. The text that comes back is checked, and customers' details the checks find are hidden before anyone else, or any other service, sees it.",
        "When you send an idea, its draft goes to that service so it can be read aloud to the review desk and the Ones Committee, with the answers to the review desk's questions, the first name of whoever answered, and the names of its files. This happens again after each change or answer, whether or not you recorded a voice note.",
      ],
    },
    {
      heading: "How long we keep it",
      paragraphs: [
        "We keep your ideas and their conversations for as long as KFintech's record-retention policy requires for business records. Drafts you don't send are archived after 30 days. Voice recordings are deleted within a day, once they are turned into text.",
      ],
    },
    {
      heading: "Your choices and questions",
      paragraphs: [
        "You can see and download everything you have shared from My ideas.",
        "For questions or complaints under KFintech's data protection policy, or to ask for a copy, correction or deletion of your data, write to KFintech's Data Protection Officer at the address given in that policy on the intranet.",
      ],
    },
  ],
} as const;
