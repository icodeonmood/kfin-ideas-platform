# 1% Club: local demo

For: the product lead, walking through the app on the test Mac. Everything you'll see is synthetic demo data.

## Start it

```bash
make up migrate seed demo
```

Open **http://localhost:3000**. Every feature is on, as at launch (DEC-088). A stack where older test runs left a feature switched off keeps it off: as Sana, switch it on in Admin. Committee appears in the menu only while the committee flow is on. `make demo` runs only on the local dev stack (`APP_ENV=dev`, and only against the local `ideas` database), and a second run changes nothing. **`make demo-reset`** starts the demo afresh: it removes only the demo's own people and everything that is theirs (their Ones records, proposals, deliveries and ideas) and takes the demo ideas' files out of the local company repo, so Find your crew has nothing left over. Run it to see the glow-up again; it only plays once.

## Sign in

Choose **Sign in with your KFintech account**. On the mock sign-in page, type the employee ID below as the username and submit. The privacy notice is already accepted for these people. Use a private window, or sign out between people.

| Username | Who | Use it for |
|---|---|---|
| `DEMO-00001` | Kavya Menon, an employee | Home, sharing, Find your crew, My ideas, Messages |
| `DEMO-00002` | Nikhil Rao, review desk | The review desk |
| `DEMO-00003` | Meera Pillai, core committee | Committee and Desk decisions; proposing in the console |
| `DEMO-00004` | Vivek Shenoy, core committee chair | Approving in the console |
| `DEMO-00005` | Demo CEO | Sponsoring a One; approving a handover pack; confirming results |
| `DEMO-00006` | Sana Qureshi, admin | Carrying out, screens, launch, kill switches |
| `DEMO-00007` | Rahul Deshpande, a manager | The manager's team view |
| `DEMO-00008` | Ananya Rao, One No. 17 | The glow-up (her tier-up to Glow has just gone through), her dashboard, the leaderboard; owner of two deliveries |
| `DEMO-00009` | Rohit Menon, founding One No. 1, tier 4 (Blaze) | A founding One's dashboard |
| `DEMO-00013` | Deepa Joshi, delivery PM | Recording each step of a build |
| `DEMO-00017` | Vikram Bhat, fix-track owner | A non-tech fix: the action plan and the numbers |

## The tour

1. **Home carousel** (Kavya): below the welcome, "What the Ones are up to". It moves only when you press Next, Previous or Play.
2. **Share an idea** (Kavya): "Share an idea" in the menu. The canvas, the strength meter and the "why we ask" notes.
3. **Find your crew** (Kavya): My ideas, then "Catch missing bank fields on SIP mandates at capture". A colleague raised the same thing, under "Colleagues are on this".
4. **My ideas as a One** (Ananya): the glow-up plays on her first visit. The spark heats from Spark orange to Glow, then her story and messages from the committee, the CEO and Kavya appear. Behind it is her tier-coloured dashboard: number, 30-day number choice, impact brief, impact so far, and the Showcase brief link. Rohit (`DEMO-00009`) shows a founding One at Blaze.
5. **The wall** (anyone): "The Ones" first, with numbers in tier colours. Names show only for people who agreed; Karthik shows as "One No. 3". Below that are ideas by stage.
6. **An idea page**: open any idea on the wall.
7. **Review desk** (Nikhil): the queue, including Kavya's courier-tracking idea, then one item.
8. **Desk decisions** (Meera): Committee in the menu, then Desk decisions. Kavya's decided idea, which can still be reconsidered for five working days.
9. **The console's Ones** (Menu, then Ones). As Vivek (chair), three items are waiting:
   - **Vikram Bhat**, a sponsored inclusion waiting for the chair: "Approve as chair".
   - **Farhan Qureshi's** tier-up to Glow, waiting for approval. The committee's message is written, and Kavya is invited to add hers at the link in her Messages.
   - **Suresh Patil's** removal, approved at yesterday's meeting and waiting for the admin. As Sana, use "Carry out and send"; the thank-you message goes to him.

   The roster shows No. 7 as resting after Gaurav retired. Each One has their own Showcase brief; Ananya's is partly filled in.
10. **Leaderboard** (Ananya): Menu, My ideas, then "The Ones leaderboard". Only Ones can see it, and a One who has not agreed to be named shows as their number (BLD-109).
11. **Manager view** (Rahul): `/my-team`, his four direct reports, counts only.
12. **Office screen** (anyone): `/constellation`, the sky of sparks, alternating with impact cards. As Sana, "Switch to ambient mode" in the console makes one spark glow every ten seconds.
13. **Launch screen** (Sana): `/launch`, then Start, with sound.
14. **Kill switches** (Sana): Admin. `ones.public` hides the Ones from the wall, home and screens. `learning.jobs` stops the learning reports.
15. **Delivery** (Meera): Menu, then Delivery. Every delivery, one in each state, and "Picked, waiting for a handover": Lakshmi's transmission-documents idea. Choose a track and "Start the handover", then fill in the pack. "Draft it with the assistant" fills the empty fields from the idea (the metric, its unit, the product and type) and lists the questions to answer; check every field, then save.
16. **The sponsor** (Demo CEO): Delivery, then "Show distributors on IRIS why an SIP registration is stuck…": Ananya has sent the pack. "Approve the pack" starts the work, and Ananya, Farhan and Deepa hear about it. Then the brokerage statements: the 90-day results are in. "Confirm these results" closes it as target met.
17. **The delivery PM** (Deepa): Delivery, then Ananya's nominee idea. "Record the current step", for example "Building: test". Choosing Shipped opens the 30- and 90-day results.
18. **A non-tech fix** (Vikram): Delivery, then the change-of-bank checklist. The action plan has one overdue milestone; "Mark done", then "It's done: send the numbers" for the sponsor to approve.
19. **Finance's confirmation** (Sana): Delivery, then the investor service request status page (closed, target met). The money waits for Finance: "Finance has confirmed the money" puts it on the wall with the Ones' impact.
20. **Lenses** (Meera or Sana): Menu, then Lenses. Ideas by line of business and by role, and the colleagues around each group, as counts only.
21. **Learning** (Sana): Admin, then "Learning reports and proposals". A new glossary term found in three ideas (IFSC) waits for the product team: approve or decline. Once approved, "Write it into the company repo" asks what it means and its other spellings; the repo writer then adds `taxonomy/glossary/GL-ifsc.md` and the line shows "In the company repo". The review desk's acceptance rates are shown, and every kind stays with a person.
22. **Points and the journey** (Kavya): My ideas, "Your points" (only she sees them), then "How an idea becomes a One": the four steps drawn as isometric blocks.
23. **The Ember** (anyone): the footer's "The Ember" link. Last month's issue is in the archive.
24. **Write The Ember** (Vivek, then Sana): "Work on this month's issue". Vivek, the chair, edits "What the committee looks for" and presses "Approve the note"; the issue is now ready. Sana, an admin who neither wrote nor approved it, reads the preview and sends it in two steps ("Send to everyone", then "Yes, send to everyone"). Changing the note after approval sends it back to the chair. The email arrives in Mailpit (http://localhost:8025) in the branded HTML, light or dark depending on the mail app.
25. **A write-up other teams can adopt** (Demo CEO, then Sneha): Delivery, then the brokerage statements. Sneha's write-up waits for the sponsor under "A write-up other teams can adopt": "Approve and publish" gives it a SOL- number and, once the repo writer and indexer run, ideas like it show it as "Already running". "Send back for changes" returns it to Sneha, who edits it and sends it again. Switch `solutions.publish` off in the console and approval says publishing is paused.
26. **Your lens** (Kavya, or anyone): My ideas, then "Your lens". Her ideas by where they are, and each group she is part of with how many ideas and colleagues are in it. Only she sees it, and it never names anyone.
27. **Friction themes by role** (Sana, then Meera): Learning, "Friction themes by role": client service's themes wait for approval; approve them. Then Lenses: under "Recurring friction themes for each role", operations executives' approved themes with how many ideas share each. No names, no idea text.
28. **Learning from the committee's decisions** (Sana, then Vivek): on Learning, "Run a report now" for "The pre-score against the core committee" and "Scoring bands". Then Vivek: Committee, then Desk decisions and "What the platform learns from your decisions". The demo has only a few scored rounds, so counts read "fewer than 5" and nothing waits; with 30 or more decisions a proposal appears here for the chair or the committee to approve or decline. Approving never changes a rule on its own.

## Shows "Coming soon"

- **Automatic tiers and lapse proposals** (console): today the committee decides each one.
- **Impact weights** (leaderboard).
- **Manager notes and nudges** (manager view).
- **Live sync with the delivery pipeline** (Delivery): steps are recorded by hand until then.
- **A drafted pack**, **evidence files**, **replies to the Friday check-in** and **a write-up other teams can adopt** (a delivery).
- **Recurring friction themes for each role** and **your own view of your groups** (Lenses).
- **Switching a kind of suggestion to automatic** (off at launch) (Learning).
- **Similar past decisions in the pre-score and briefs**, **guidance notes drafted from the committee's reasons**, **seeing a proposal's effect on the fairness gaps**, **financial band edges** and **writing an approved rule change into the company repo** (Learning from your decisions).

## Good to know

- Model calls use the fake route, so the assistant's suggestions on new ideas are sample text.
- The demo's measured impact is made up and marked as demo data.
- A check of the whole tour runs with `cd apps/web && DEMO_TOUR=1 npx playwright test e2e/demo-tour.spec.ts`. It leaves the glow-up unplayed.
- **Running the tests on this Mac:** `make demo-remove`, then `make lint test e2e eval`, then `make demo`. With the demo loaded, Meera and Vivek join every new scoring round, so the committee tests wait for scores that never come (BLD-154).
- **"Adding research files is paused"** usually means the virus scanner stopped answering and uploads switched themselves off (an admin can also pause them by hand). They stay off until someone switches them back: once ClamAV is healthy, Sana turns `attachments.upload` on in Admin.
