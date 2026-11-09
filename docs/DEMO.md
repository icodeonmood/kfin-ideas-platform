# 1% Club: local demo

For: the product lead, walking through the app on the test Mac. Everything you'll see is synthetic demo data.

## Start it

```bash
make up migrate seed demo
```

Open **http://localhost:3000**. `make demo` runs only on the local dev stack (`APP_ENV=dev`), and a second run changes nothing. **`make demo-reset`** starts the demo afresh. It also removes every One in the local database, so run it to see the glow-up again; it only plays once.

## Sign in

Choose **Sign in with your KFintech account**. On the mock sign-in page, type the employee ID below as the username and submit. The privacy notice is already accepted for these people. Use a private window, or sign out between people.

| Username | Who | Use it for |
|---|---|---|
| `DEMO-00001` | Kavya Menon, an employee | Home, sharing, Find your crew, My ideas, Messages |
| `DEMO-00002` | Nikhil Rao, review desk | The review desk |
| `DEMO-00003` | Meera Pillai, core committee | Desk decisions; proposing in the console |
| `DEMO-00004` | Vivek Shenoy, core committee chair | Approving in the console |
| `DEMO-00005` | Demo CEO | Sponsoring a One |
| `DEMO-00006` | Sana Qureshi, admin | Carrying out, screens, launch, kill switches |
| `DEMO-00007` | Rahul Deshpande, a manager | The manager's team view |
| `DEMO-00008` | Ananya Rao, One No. 17 | The glow-up (her tier-up to Glow has just gone through), her dashboard, the leaderboard |
| `DEMO-00009` | Rohit Menon, founding One No. 1, tier 4 (Blaze) | A founding One's dashboard |

## The tour

1. **Home carousel** (Kavya): below the welcome, "What the Ones are up to". It moves only when you press Next, Previous or Play.
2. **Share an idea** (Kavya): "Share an idea" in the menu. The canvas, the strength meter and the "why we ask" notes.
3. **Find your crew** (Kavya): My ideas, then "Catch missing bank fields on SIP mandates at capture". A colleague raised the same thing, under "Colleagues are on this".
4. **My ideas as a One** (Ananya): the glow-up plays on her first visit. The spark heats from Spark orange to Glow, then her story and messages from the committee, the CEO and Kavya appear. Behind it is her tier-coloured dashboard: number, 30-day number choice, impact brief, impact so far, and the Showcase brief link. Rohit (`DEMO-00009`) shows a founding One at Blaze.
5. **The wall** (anyone): "The Ones" first, with numbers in tier colours. Names show only for people who agreed; Karthik shows as "One No. 3". Below that are ideas by stage.
6. **An idea page**: open any idea on the wall.
7. **Review desk** (Nikhil): the queue, including Kavya's courier-tracking idea, then one item.
8. **Desk decisions** (Meera): Kavya's decided idea, which can still be reconsidered for five working days.
9. **The console's Ones** (Menu, then Ones). As Vivek (chair), three items are waiting:
   - **Vikram Bhat**, a sponsored inclusion waiting for the chair: "Approve as chair".
   - **Farhan Qureshi's** tier-up to Glow, waiting for approval. The committee's message is written, and Kavya is invited to add hers at the link in her Messages.
   - **Suresh Patil's** removal, approved at yesterday's meeting and waiting for the admin. As Sana, use "Carry out and send"; the thank-you message goes to him.

   The roster shows No. 7 as resting after Gaurav retired. Each One has their own Showcase brief; Ananya's is partly filled in.
10. **Leaderboard** (Ananya): Menu, My ideas, then "The Ones leaderboard". Only Ones can see it, and a One who has not agreed to be named shows as their number (BLD-109).
11. **Manager view** (Rahul): `/my-team`, his four direct reports, counts only.
12. **Office screen** (anyone): `/constellation`, the sky of sparks, alternating with impact cards. As Sana, "Switch to ambient mode" in the console makes one spark glow every ten seconds.
13. **Launch screen** (Sana): `/launch`, then Start, with sound.
14. **Kill switches** (Sana): Admin. `ones.public` hides the Ones from the wall, home and screens.

## Shows "Coming soon"

- **Automatic tiers and lapse proposals** (console): today the committee decides each one.
- **Your points** (a One's dashboard).
- **Impact weights** (leaderboard).
- **Manager notes and nudges** (manager view).

## Good to know

- Model calls use the fake route, so the assistant's suggestions on new ideas are sample text.
- The demo's measured impact is made up and marked as demo data.
- A check of the whole tour runs with `cd apps/web && DEMO_TOUR=1 npx playwright test e2e/demo-tour.spec.ts`. It leaves the glow-up unplayed.
