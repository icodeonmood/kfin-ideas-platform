# Privacy notice 0.2: changes for Legal and the DPO

The notice every person accepts at first sign-in, before Home (`apps/web/src/content/privacy-notice.ts`, BLD-A232). Version 0.1-draft becomes **0.2-draft**: the page reads "Version 0.2-draft (draft, awaiting Legal sign-off)", and everyone who accepted 0.1-draft is asked to accept again at their next sign-in. The version is pinned in `.env.example` and `scripts/uat/rehearse.sh` too, and the go/no-go report counts any version ending in "draft" as not live.

**On every server that runs this build, `PRIVACY_NOTICE_VERSION` in its `.env` must read `0.2-draft`.** The notice page refuses to show a notice whose version differs from the configured one, so a server left on `0.1-draft` cannot take anyone through first sign-in.

What changed: four topics, corrected to the product lead's decisions of 16 and 17 November and to how the platform learns. Sentences not listed here are unchanged.

## Changed and new sentences

| Section | Old sentence (or "new") | New sentence | Decision it follows |
|---|---|---|---|
| What we use | What you share here: your ideas, comments, files and choices such as teaming up with colleagues. | What you share here: your ideas, voice notes, files, messages in an idea's conversation, and choices such as teaming up with colleagues. | DEC-108 (voice notes); F-COPY.vocabulary ("conversation", not "comments") |
| Why we use it | Outside the app, your ideas carry a contributor code instead of your name. | We store your ideas against a contributor code, and keep the link to your name separately. | DEC-106 (1): nothing writes ideas outside the platform any more; DEC-104: names show inside it; non-negotiable 6 (the code-to-employee map stays in the database). The retention line still relies on the code |
| Why we use it | Your name is shown on the public wall only if you agree. | Removed here; replaced by the first two sentences of "Who sees what" | DEC-104 |
| Why we use it | Before any AI assistant reads your idea, names and personal details are replaced with labels. | Before any AI assistant reads your idea, names and personal details in the text are replaced with labels. | DEC-108 (5): text is masked, audio is not |
| Why we use it | new | A voice recording is the one exception, because a recording can't be masked. See Voice notes below. | DEC-108 (5) |
| Who sees what | new (section) | Your name shows on your ideas, on crew cards and on your requests to team up. | DEC-104; P-PRODUCT.privacy |
| Who sees what | new | It also shows on the Wall next to your shared ideas, unless you turn that off in Profile. | DEC-104; Profile's switch "Show my name next to my ideas" |
| Who sees what | new | The review desk and the Ones Committee see your name. | DEC-104 |
| Who sees what | new | Your words, as you typed or said them, go only to you, the review desk and the Ones Committee. | DEC-104; P-PRODUCT.privacy ("Their own words (raw text, voice)") |
| Who sees what | new | Everyone else sees the short summary. | DEC-104; P-PRODUCT.privacy |
| Who sees what | new | Your crew also sees the idea's checked files and its conversation. | DEC-104; P-PRODUCT.privacy (a file with a customer detail is the exception, below) |
| Who sees what | new | Your points are private to you. | DEC-104; P-PRODUCT.privacy |
| Never share | The platform blocks them, but please don't type them. | Don't type them. | DEC-103: details are hidden, not stopped; F-COPY.voice (no "please") |
| Never share | new | If a PAN, Aadhaar, folio, account or phone number or a customer's email address slips in, it is hidden. | DEC-103; L-HIDE (the kinds the checks find; addresses stay in the ask above but are not claimed as found) |
| Never share | new | It is masked before any other person or service sees your text. | DEC-103 |
| Never share | new | The full value is stored encrypted, and only you can see it. | DEC-103 |
| Never share | new | A file that holds a customer detail opens only for you, the review desk and the Ones Committee. | DEC-107 |
| Voice notes | new (section) | If you record a voice note, it goes to an Indian speech service to turn it into text. | DEC-108 (5); DEC-096 (no vendor named) |
| Voice notes | new | You can check the text before you send it. | DEC-108 (1); the same words the recorder shows before a recording |
| Voice notes | new | The recording goes as you spoke it, because a recording can't be masked. | DEC-108 (5); non-negotiable 2's voice exception |
| Voice notes | new | Text we send to that service for translation or to be read aloud is masked first. | DEC-108 (3), (4), (5) |
| Voice notes | new | Every transcript is masked as it comes back, before any other person or service sees it. | DEC-108 (5); DEC-103 |
| How your ideas improve the suggestions | new (section) | When the review desk changes something the assistant suggested, such as the sorting, we keep that change as a worked example for later suggestions. | ARCHITECTURE §5.1 (corrections, plan P6) |
| How your ideas improve the suggestions | new | Names and personal details in it are replaced with labels. | §5.1; the desk's notes are tagged before they are stored |
| How your ideas improve the suggestions | new | We also count how often suggestions are accepted, and look across ideas for new terms and areas. | BLD-121 (acceptance reports, glossary and area-tag proposals) |
| How your ideas improve the suggestions | new | The product team approves or declines every change these point to. | BLD-121 |
| How your ideas improve the suggestions | new | People decide every change. | Non-negotiable 5; BLD-121 |
| How your ideas improve the suggestions | new | Nothing changes by itself. | BLD-121; §5.6 (autonomy off at launch) |

## What the notice deliberately does not say

It names no speech vendor (DEC-096). It does not claim India-hosted processing, no retention or no training by the speech service: DEC-108 records these only as requests made to the vendor, not as agreed terms. It says nothing about any model provider's training.

## Still waiting for the DPO

These three sentences are unchanged, word for word, until the DPO's lines arrive.

| Section | Sentence | Owner |
|---|---|---|
| Why we use it | Your contribution history is not used in performance appraisal unless HR policy says so. (To be confirmed by HR.) | DPO, with HR |
| How long we keep it | As long as KFintech's record-retention policy requires. If you leave KFintech, the link between your name and your contributor code is deleted, so your ideas stay but no longer point to you. (Retention period to be confirmed by Legal.) | DPO, with Legal |
| Your choices and questions | For questions or complaints under KFintech's data protection policy, contact the Data Protection Officer. (Contact details to be confirmed by Legal.) | DPO, with Legal |

When they arrive, one commit replaces these three sentences, sets the version to **0.2** with `draft: false` in `privacy-notice.ts`, and sets `PRIVACY_NOTICE_VERSION=0.2` in `.env.example` and `scripts/uat/rehearse.sh`. The test `services/worker/tests/test_a232_privacy_notice.py` then expects no "to be confirmed" line. Legal and the DPO sign off the full text before that commit.
