# 1% Club: local demo

For: the product lead, walking through the app on the test Mac. Every person, idea and number you see is synthetic.

## Start it

```bash
make up migrate seed
make demo DEMO_SET=1pc
```

Open **http://localhost:3000/sign-in**. `DEMO_SET=1pc` loads the 1% Club seed (`services/worker/bootstrap/club_seed.py`); every `make demo…` command on this stack needs it. Without it, `make demo` loads the old demo instead, whose people (`DEMO-00001`…) are not the ones the walks use (see "The old demo" below).

A second `make demo DEMO_SET=1pc` changes nothing; it prints "already loaded". **`make demo-reset DEMO_SET=1pc`** takes out the seed's people and everything that is theirs, then loads it again, in one go: if the load fails, the seed stays as it was. Run it to see a first visit or a tier-up moment again; each plays once. If the switch `matching.show` is off, loading or resetting stops and changes nothing: switch it on in Admin as Kunal (or as `SYN-00001` before the first load), or with the `make killswitch` line the message prints, then run it again. `make demo` runs only on the local dev stack (`APP_ENV=dev`, and only against the local `ideas` database).

## Sign in

1. At **http://localhost:3000/sign-in**, choose **Use single sign-on**. (The page at http://localhost:3000 is the Landing page; it has no sign-in link.)
2. On the mock sign-in page, type the employee ID from the table below as the username, exactly as written (`SYN-1` then four digits), and submit.
3. Use a private window for each person, or sign out between people.

If the privacy notice shows first, read it and choose **I have read this — continue**. The seed accepts the notice that was current when it loaded, so after a notice change each person sees the new one once.

`make seed` also loads a synthetic directory, `SYN-00001` onwards, and some of those people have roles. They have no ideas, crews or Inbox items. For the walks, use the `SYN-100xx` people below; `make demo DEMO_SET=1pc` prints this list when it loads.

| Username | Who | Use it for |
|---|---|---|
| `SYN-10001` | Tanvi Deshmukh, an employee | A sharer with ideas at every stage: Home, Share a problem, My ideas, Inbox, an idea's conversation |
| `SYN-10002` | Harish Venkatesan, review desk | Review desk: to review, waiting on the sharer (one overdue), answered, decided |
| `SYN-10003` | Lavanya Krishnan, review desk | Review desk, the second reviewer |
| `SYN-10004` | Manoj Agarwal, Ones Committee | Ones Committee: decisions inside the window (one extended), expired ones and a reversal |
| `SYN-10005` | Shalini Bose, Ones Committee | Ones Committee, the second member |
| `SYN-10006` | Kunal Malhotra, admin | Admin (kill switches and roles); the launch screen at `/display/launch`: Full screen, then Start (it plays a sound) |
| `SYN-10007` | Hyderabad Office Screen | The office screen at `/display/office` (choose the Full screen icon button on the screen). It can also open `/display/launch` |
| `SYN-10008` | Gopal Iyengar, One No. 15 | A build team lead; Your One dashboard |
| `SYN-10009` | Rekha Saxena, a Founding One (No. 4) | A lead with a team-up request waiting in her Inbox |
| `SYN-10010` | Varun Chopra, One No. 11 | A shipped fix; Your One dashboard |
| `SYN-10012` | Siddharth Menezes, a new One | A One whose number is still open |
| `SYN-10013` | Aparna Hegde, a Founding One | A Founding One whose idea is being built |
| `SYN-10017` | Charulata Sen, an employee | Hides her name on the Wall |
| `SYN-10018` | Dinesh Kamath, One No. 8 | His tier has just risen. The moment plays once when he opens Your One dashboard |
| `SYN-10025` | Kiran Bhatia, an employee | A sharer the review desk asks first |
| `SYN-10026` | Sana Qureshi, an employee | Her first visit to Home |

`SYN-10011`, `SYN-10014` to `SYN-10016` and `SYN-10019` to `SYN-10024` are colleagues with ideas, crews and team-ups around the people above.

## Before the gates run on this Mac

The tests expect a fresh seed, and a reset loses whatever a walk changed, so the order is fixed:

1. `make demo-remove DEMO_SET=1pc`
2. `make lint test e2e eval` (`make e2e` loads the seed fresh for its own run)
3. `make demo-reset DEMO_SET=1pc`
4. `docker image prune -f --filter label=org.kfin.project=kfin-ideas` (each build adds about 1 GB of images)

Lane A asks you before running this on the walk stack, as a walk may be in progress.

## Good to know

- Model calls use the fake route (`LLM_MODE=fake`), so the assistant's drafts from new words are sample text. Similar ideas use test vectors (`EMBEDDINGS_MODE=hash`), so matches are not meaningful.
- Customer details in the seed's words are made-up values that only look like a folio, PAN or phone number. They are hidden as they would be for real ones.
- **"Adding files is paused"** usually means the virus scanner stopped answering and uploads switched themselves off (an admin can also pause them by hand). A switch the platform turns off stays off. Once ClamAV is healthy, Kunal turns `attachments.upload` on in Admin.

## The old demo

`make demo` without `DEMO_SET` loads the demo from before the 1% Club design (DEC-102): people `DEMO-00001` to `DEMO-00017` (Kavya Menon, Nikhil Rao and others), and the opt-in check `apps/web/e2e/demo-tour.spec.ts`. The walk stack does not load it, and those usernames do not sign in there. Its tour is in this file's history: `git show 1710f7ab:docs/DEMO.md`.
