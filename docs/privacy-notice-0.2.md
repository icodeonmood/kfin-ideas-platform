# Privacy notice 0.2: changes for Legal and the DPO

This is the notice every person accepts at first sign-in, before Home (`apps/web/src/content/privacy-notice.ts`, BLD-A232). Version 0.1-draft becomes **0.2-draft**, and the page reads "Version 0.2-draft (draft, awaiting Legal sign-off)". After the install, everyone who accepted 0.1-draft is sent to the notice on the next page they open and asked to accept again. The version is also pinned in `.env.example` and `scripts/uat/rehearse.sh`. The go/no-go report counts any version ending in "draft" as not live.

**On every server that runs this build, `PRIVACY_NOTICE_VERSION` in the app env file must read `0.2-draft`.** The notice page will not show a notice whose version differs from the configured one. A server left on `0.1-draft` therefore cannot take anyone through first sign-in. `scripts/uat/deploy.sh` now stops at preflight when the two versions differ. Where the install does not use that script, check this setting by hand.

What changed: four topics, corrected to the product lead's decisions of 16 and 17 November, and then to an independent review against the code (the B and S findings below). Sentences not listed here are unchanged. Six sentences are still open: three wait for the product lead and three for the DPO.

## Changed and new sentences

| Section | Old sentence (or "new") | New sentence | Decision it follows |
|---|---|---|---|
| What we use | What you share here: your ideas, comments, files and choices such as teaming up with colleagues. | What you share here: your ideas, voice notes, files, messages in an idea's conversation, and choices such as teaming up with colleagues. | DEC-108 (voice notes); F-COPY.vocabulary ("conversation", not "comments") |
| What we use | new | How you'd like us to refer to you, if you choose to tell us in Profile. | DEC-108 (3): asked once in Profile, stored in `person_settings.refer_as` (review B4) |
| Why we use it | Outside the app, your ideas carry a contributor code instead of your name. | Inside 1% Club, your ideas are stored under a contributor code, and the link from that code to you is kept in a separate table. | DEC-106 (1): nothing writes ideas outside the platform any more; DEC-104: names show inside it; non-negotiable 6. See the note for the DPO below (review S4) |
| Why we use it | Your name is shown on the public wall only if you agree. | Removed here; replaced by the first two sentences of "Who sees what" | DEC-104 |
| Why we use it | Before any AI assistant reads your idea, names and personal details are replaced with labels. The assistant never sees them. | Our checks look for names and personal details in your text and replace them with labels before the AI assistant reads it. | Non-negotiable 2 (tagging before every model call). The checks can miss, so nothing is promised absolutely (L-HIDE.detect, L-HIDE.rules/7; review B7) |
| Why we use it | new | A voice recording is the one exception, because a recording can't be masked. | DEC-108 (5). **Waiting for the product lead (review B3)** |
| Why we use it | new | See Voice notes below. | **Waiting for the product lead (review B3)** |
| Who sees what | new (section) | Your name shows on your ideas, on crew cards and on your requests to team up. | DEC-104; P-PRODUCT.privacy |
| Who sees what | new | It also shows on the Wall next to your shared ideas, unless you turn that off in Profile. | DEC-104; Profile's switch "Show my name next to my ideas" |
| Who sees what | new | The review desk and the Ones Committee see your name. | DEC-104 |
| Who sees what | new | Only you, the review desk and the Ones Committee read your words. | DEC-104; P-PRODUCT.privacy ("Their own words (raw text, voice)"). Hidden customer details stay hidden from the desk and the committee too (L-HIDE.rules/3) |
| Who sees what | new | Everyone else sees the short summary. | DEC-104; P-PRODUCT.privacy |
| Who sees what | new | Your crew also sees the idea's checked files, its conversation, the review desk's questions and your answers, and the decision with its reason. | DEC-104; P-PRODUCT.privacy (review S3) |
| Who sees what | new | A file that holds a customer detail is the exception (see Never share). | DEC-107 (review S3) |
| Who sees what | new | Once a build team is chosen, it sees the conversation too, and a colleague you mention in a message sees that message. | L-CONVO/2, /6; `convo/access.py` (BLD-F052; review S3) |
| Who sees what | new | Your points are private to you. | DEC-104; P-PRODUCT.privacy |
| Never share | The platform blocks them, but please don't type them. | Don't type or say them. | DEC-103: details are hidden, not stopped. DEC-108 (5): the recording is not hidden. F-COPY.voice: no "please" (review S1) |
| Never share | new | If you include a customer's PAN, Aadhaar, folio, account or phone number, or their email address, our checks look for it and hide it before any other person or service sees your text. | DEC-103; L-HIDE.rules/1, /3. These are the kinds the checks look for. Addresses stay in the ask above but are not claimed as found (review B7) |
| Never share | new | The review desk can hide one the checks missed. | L-HIDE.rules/7 (review B7) |
| Never share | new | The full detail is stored encrypted, and only you can see it. | DEC-103; L-HIDE.rules/4 |
| Never share | new | If it isn't a customer's detail, such as a scheme code, you can choose Show it and give a reason. | DEC-103; L-HIDE.rules/6. The three reasons are a scheme or product code, an internal reference, or made up for the example (review B1) |
| Never share | new | It is then no longer hidden, and the review desk sees that you showed it and why. | L-HIDE.rules/6. The shown value returns to every copy, and the reason is logged with the idea for the desk (review B1) |
| Never share | new | A file that holds a customer detail is not hidden. | DEC-107. The black-out copy (`files.blackout`) is off at launch (review B1) |
| Never share | new | It opens only for you, the review desk and the Ones Committee, and they see it as it is. | DEC-107 (review B1) |
| Voice notes and listening | new (section) | If you record a voice note, it goes to an Indian speech service to turn it into text. | DEC-108 (5); DEC-096 (no vendor named) |
| Voice notes and listening | new | You can check the text before you send it. | DEC-108 (1). The recorder shows the same words before a recording |
| Voice notes and listening | new | The recording goes as you spoke it, because a recording can't be hidden. | DEC-108 (5); non-negotiable 2's voice exception |
| Voice notes and listening | new | So don't say a customer's details in a voice note. | DEC-108 (5); DEC-103 (review S1) |
| Voice notes and listening | new | If you chose 'she' or 'he' in Profile, that goes to the service with your voice note, so its English copy refers to you correctly. | DEC-108 (3); `speech/prefs.py`. Only "she" or "he" is sent; "they" and "Prefer not to say" send nothing (review B4) |
| Voice notes and listening | new | Text we send to that service for translation or to be read aloud is masked first. | DEC-108 (3), (4), (5). **Waiting for the product lead (review B3)** |
| Voice notes and listening | new | The text that comes back is checked, and customers' details the checks find are hidden before anyone else, or any other service, sees it. | DEC-108 (5); DEC-103. F-COPY.vocabulary: no "transcript" (review S2) |
| Voice notes and listening | new | When you send an idea, its draft, with customers' details hidden, also goes to that service so it can be read aloud to the review desk. | DEC-108 (4); L-LISTEN. `speech/listen.py` makes the audio when an idea is sent; `desk.listen` and `speech.hosted` are on at launch (review B2) |
| Voice notes and listening | new | This happens whether or not you recorded a voice note. | DEC-108 (4) (review B2) |
| How your ideas improve the suggestions | new (section) | When the review desk changes something the assistant suggested, such as the sorting, we keep that change as a worked example for later suggestions. | **Waiting for the product lead (review B5).** The ask's sources, ARCHITECTURE §5.1 and BLD-121, are retired (DEC-106; `docs/SHIP_PLAN_1PC.md` §6.2) |
| How your ideas improve the suggestions | new | Names and personal details in it are replaced with labels. | **Waiting for the product lead (review B5)** |
| How your ideas improve the suggestions | new | We also count how often suggestions are accepted, and look across ideas for new terms and areas. | **Waiting for the product lead (review B5)** |
| How your ideas improve the suggestions | new | The product team approves or declines every change these point to. | **Waiting for the product lead (review B5)** |
| How your ideas improve the suggestions | new | People decide every change. | **Waiting for the product lead (review B5)** |
| How your ideas improve the suggestions | new | Nothing changes by itself. | **Waiting for the product lead (review B5)** |

## Waiting for the product lead

These sentences are in 0.2-draft as they stand. The review found each one inaccurate, and each needs the product lead's call before it changes. Changing them later than tonight's install means another version, and everyone accepts again.

| Finding | Sentence in 0.2-draft | What is wrong | The reviewer's proposed replacement |
|---|---|---|---|
| B3 | A voice recording is the one exception, because a recording can't be masked. See Voice notes below. | Text sent to the speech service is checked only by the patterns: customer details, plus ARN, EUIN, IFSC and KFin addresses. Names are not replaced, whether a colleague's or a customer's. So the recording is not the one exception. | Voice notes and read-aloud work differently: see below. |
| B3 | Text we send to that service for translation or to be read aloud is masked first. | The same: names in that text go to the service as written. | Before text goes to that service, to make the English copy or to be read aloud, customers' details in it are hidden. Other names in it, such as a colleague's, are not. |
| B5 | The whole section "How your ideas improve the suggestions" (six sentences above) | The learning loops are retired (DEC-106; `SHIP_PLAN_1PC.md` §6.2; `learning.run` is no longer scheduled). The 1% Club review desk writes no corrections, and the sharer, not the desk, confirms the sorting. What is kept is a count of how often people keep or change each suggested sorting field (L-SORT.rules/8, L-AUDIT.metrics). | Heading "How the assistant gets better": "We count how often people keep or change the assistant's suggestions, such as the sorting, to see how well it works." and "People decide any change to how the assistant works. Nothing changes by itself." |
| B6 | You can see and download everything you have shared from My ideas. | This sentence is unchanged from 0.1. There is no download or export in My ideas or anywhere else. | You can see the ideas you have shared in My ideas. |

## What the notice deliberately does not say

The notice names no speech vendor (DEC-096). In "an Indian speech service", the word "Indian" describes the company, not where the processing happens. The notice does not claim that processing is India-hosted, or that the speech service keeps nothing or trains on nothing: DEC-108 records these only as requests made to the vendor, not as agreed terms. It says nothing about any model provider's training. Until B3 is settled, it does not tell people that names in text sent to the speech service go as written.

## Still waiting for the DPO

These three sentences stay word for word until the DPO's lines arrive.

| Section | Sentence | Owner |
|---|---|---|
| Why we use it | Your contribution history is not used in performance appraisal unless HR policy says so. (To be confirmed by HR.) | DPO, with HR |
| How long we keep it | As long as KFintech's record-retention policy requires. If you leave KFintech, the link between your name and your contributor code is deleted, so your ideas stay but no longer point to you. (Retention period to be confirmed by Legal.) | DPO, with Legal |
| Your choices and questions | For questions or complaints under KFintech's data protection policy, contact the Data Protection Officer. (Contact details to be confirmed by Legal.) | DPO, with Legal |

**Note for the DPO: the leaver promise in the retention line is not built.** Today nothing deletes the link between a person and their contributor code when they leave. The HR import marks leavers inactive and never deletes them, and nothing in the platform deletes rows from the code-to-person table (`contributor_map`). A person's own unmasked words are also stored against their user ID (`idea_words_sealed.owner_user_id`), not against the contributor code. Deleting the code link alone would therefore not stop those words pointing to them. The retention line needs either that work or new wording. The placeholder above is left exactly as it is for your text.

When the DPO's lines arrive, one commit makes these changes:
- it replaces the three sentences above;
- it sets the version to **0.2** with `draft: false` in `privacy-notice.ts`;
- it sets `PRIVACY_NOTICE_VERSION=0.2` in `.env.example`, in `scripts/uat/rehearse.sh` and in every server's app env file.

The test `services/worker/tests/test_a232_privacy_notice.py` then expects no "to be confirmed" line. Legal and the DPO sign off the full text before that commit.
