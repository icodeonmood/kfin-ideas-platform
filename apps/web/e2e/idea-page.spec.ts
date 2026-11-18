/**
 * `/ideas/:id`: S-06 for the sharer, S-09 for anyone else (P-ROUTES.screens; copy: reference/copy/Status.md,
 * PhoneStatus.md, Idea.md, PhoneIdea.md). V-ACC.track/1, /3, /6 and /7 as the sharer sees them, the merged idea
 * (L-MERGE.effects/1), S-09's privacy (S-09.rules/1), the way back (P-ROUTES.state, J-BROWSE/2 and /5), dialogs
 * (V-ACC.visual/11), the phone boards and axe (V-ACC.visual/4). The page is read on the server, so the tests read
 * Tanvi's seeded ideas (e2e/club.ts) and change nothing: Withdraw is opened and kept, Restore is only shown.
 */
import { expect, test, type Page } from "@playwright/test";

import { CLUB, clubLoaded, esc, NO_SEED, seededIdea, type IdeaKey } from "./club";
import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

const isPhone = (name: string) => name.startsWith("phone");
const soon = expect.configure({ timeout: 15_000 });
let seed = false;

test.beforeAll(async () => {
  seed = await clubLoaded();
});

const here = (page: Page) => {
  const u = new URL(page.url());
  return u.pathname + u.search;
};

/** Opens a seeded idea as Tanvi, the way a list opens it, and waits for the clean address. */
async function openIdea(page: Page, key: IdeaKey, query = "") {
  const idea = await seededIdea(key);
  await signIn(page, CLUB.tanvi);
  await page.goto(`/ideas/${idea.ref}${query}`);
  await soon.poll(() => here(page)).toBe(`/ideas/${idea.ref}`);
  return idea;
}

type Decision = {
  decision: { reason: string | null; reason_heading: string; by_line: string };
  reversal: { note: string | null } | null;
  lines: {
    committee_line: string | null;
    reversal: { title: string; note_heading: string; was_line: string; final_line: string } | null;
  } | null;
};

/** Lane B's decision for the signed-in sharer: what S-06 must show word for word (V-ACC.track/6). */
async function decisionOf(page: Page, ref: string): Promise<Decision> {
  const res = await page.request.get(`/api/ideas/${ref}/decision`);
  expect(res.ok()).toBe(true);
  return (await res.json()) as Decision;
}

test.describe("S-06 and S-09 on the 1% Club seed", () => {
  test.describe.configure({ timeout: 90_000 });
  test.beforeEach(() => test.skip(!seed, NO_SEED));

  test("S-06.states just shared, V-ACC.track/1, V-ACC.visual/4: the next step, the edit window and the way back to the filtered list", async ({
    page,
  }, info) => {
    const t5 = await openIdea(
      page,
      "T5",
      `?from=my-ideas&back=${encodeURIComponent("/my-ideas?filter=with_review_desk&row=X")}`,
    );
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeVisible();
    if (isPhone(info.project.name)) {
      await expect(
        page.getByRole("link", { name: "Back to My ideas, With the review desk" }),
      ).toHaveAttribute("href", "/my-ideas?filter=with_review_desk&row=X");
    } else {
      const crumb = page.getByRole("navigation", { name: "Breadcrumb" });
      await expect(crumb.getByRole("link", { name: "My ideas, With the review desk" })).toHaveAttribute(
        "href",
        "/my-ideas?filter=with_review_desk&row=X",
      );
      await expect(crumb.getByText(t5.ref, { exact: true })).toHaveAttribute("aria-current", "page");
    }
    await expect(page.getByText("With the review desk", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/^The review desk will look at it by \w+day \d+ \w+\.$/)).toBeVisible();
    if (isPhone(info.project.name)) {
      // PhoneStatus.md: the shorter lines, the reference line under the title and Copy reference
      await expect(page.getByText("We’ll tell you on Teams and by email.", { exact: true })).toBeVisible();
      await expect(
        page.getByText(new RegExp(`^Reference ${esc(t5.ref)}, shared \\w+day \\d+ \\w+, `)),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: `Copy reference ${t5.ref}` })).toBeVisible();
      await expect(
        page.getByText(
          /^Open to changes until \w+day \d+ \w+\. Edit or withdraw it before the review desk opens it\.$/,
        ),
      ).toBeVisible();
      await expect(
        page.getByText(
          "No messages yet. If the review desk has a question, it shows up here and in your Inbox.",
          {
            exact: true,
          },
        ),
      ).toBeVisible();
    } else {
      await expect(
        page.getByText("We’ll tell you on Teams and by email when anything changes."),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: `Copy reference ${t5.ref}` })).toBeHidden();
    }
    await expect(page.getByRole("link", { name: "Edit it" })).toHaveAttribute(
      "href",
      `/ideas/${t5.ref}/edit`,
    );
    await expect(page.getByRole("button", { name: "Withdraw" })).toBeVisible();
    if (!isPhone(info.project.name)) {
      await expect(
        page.getByText(
          /^Open to changes until \w+day \d+ \w+\. Edit or withdraw it any time before the review desk/,
        ),
      ).toBeVisible();
    }
    await expect(page.getByText(/^\d+ days? left$/)).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "What you shared" })).toBeVisible();
    await expect(
      page.getByText(
        "If the review desk puts it on the Wall, everyone at KFintech sees this short summary. Your own words stay with you and the review desk.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "You and the review desk" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open the conversation" })).toHaveAttribute(
      "href",
      `/ideas/${t5.ref}/conversation`,
    );
    await expect(
      page.getByRole("heading", { level: 2, name: "Colleagues on something similar" }),
    ).toBeVisible();
    await expectNoSeriousAxeIssues(page);
  });

  test("S-06.rules/2 (L-SUBMIT.withdraw): Withdraw confirms in place, with an optional reason; Keep it shared leaves it shared", async ({
    page,
  }) => {
    await openIdea(page, "T5");
    await page.getByRole("button", { name: "Withdraw" }).click();
    const form = page.getByRole("form", { name: "Withdraw this idea?" });
    await expect(form).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(form.getByText("It goes back to your drafts and nobody else will see it.")).toBeVisible();
    await expect(form.getByRole("textbox", { name: /Why are you withdrawing it\?/ })).toBeFocused();
    await expect(form.getByRole("button", { name: "Withdraw it" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await form.getByRole("button", { name: "Keep it shared" }).click();
    await expect(form).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Withdraw" })).toBeFocused();
  });

  test("S-06.states questions, V-ACC.track/3, C-QCARD.anatomy: the questions card with its countdown and Answer the questions; the window has closed", async ({
    page,
  }) => {
    const t6 = await openIdea(page, "T6");
    await expect(page.getByText("Needs you", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Harish has 3 questions for you" })).toBeVisible();
    await expect(page.getByText("Answer goes to").first()).toBeVisible();
    // C-QCARD.anatomy/1 and /4 (lane B's card, BLD-E051): the countdown is the header's pill, the deadline line alone
    await expect(page.getByText(/^(?:\d+ days?|\d{2}:\d{2}) left$/).first()).toBeVisible();
    await expect(
      page.getByText(/^Answer by \w+day \d+ \w+, .+\. One at a time, typed or spoken\.$/).first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Answer the questions" })).toHaveAttribute(
      "href",
      `/ideas/${t6.ref}/answer`,
    );
    // Status.md: "Open the conversation" beside the card's heading, the desk's line under it, said once (BLD-E045)
    const conv = page.getByRole("region", { name: "You and the review desk" });
    await expect(conv.getByRole("link", { name: "Open the conversation" })).toHaveAttribute(
      "href",
      `/ideas/${t6.ref}/conversation`,
    );
    await expect(
      conv.getByText(
        /^The review desk opened it on \w+day \d+ \w+, so the idea itself can’t be changed now\./,
      ),
    ).toBeVisible();
    await expect(page.getByText(/^The review desk opened it on /)).toHaveCount(1);
    await expect(page.getByRole("link", { name: "Edit it" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Withdraw" })).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
  });

  test("S-06.states picked and not now, V-ACC.track/6: the sentence, the reason word for word and the committee line", async ({
    page,
  }) => {
    const t7 = await openIdea(page, "T7");
    const d7 = await decisionOf(page, t7.ref);
    await expect(page.getByText("Picked. A team is being chosen to build it.")).toBeVisible();
    await expect(page.getByText(/Harish from the review desk picked it on \w+day \d+ \w+\./)).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: d7.decision.reason_heading })).toBeVisible();
    await expect(page.getByText(`“${d7.decision.reason}”`)).toBeVisible();
    if (d7.lines?.committee_line) await expect(page.getByText(d7.lines.committee_line)).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    const t8 = await seededIdea("T8");
    await page.goto(`/ideas/${t8.ref}`);
    const d8 = await decisionOf(page, t8.ref);
    await expect(
      page.getByText(/^Not now\. The review desk looks at it again on \w+day \d+ \w+( \d{4})?\.$/),
    ).toBeVisible();
    await expect(page.getByText(/Lavanya’s full reason is below\./)).toBeVisible();
    await expect(page.getByText(`“${d8.decision.reason}”`)).toBeVisible();
    // The window closed, so the committee line is gone (lines.committee_line is null)
    expect(d8.lines?.committee_line ?? null).toBeNull();
    await expect(page.getByText(/^The Ones Committee can review this decision/)).toHaveCount(0);
  });

  test("S-06.states reversed, V-ACC.committee/4: the committee's card, its note, what it was and This is final", async ({
    page,
  }) => {
    const t9 = await openIdea(page, "T9");
    const d = await decisionOf(page, t9.ref);
    const r = d.lines!.reversal!;
    await expect(page.getByRole("heading", { name: r.title })).toBeVisible();
    await expect(page.getByText(`“${d.reversal!.note}”`)).toBeVisible();
    await expect(page.getByText(r.note_heading)).toBeVisible();
    await expect(page.getByText(r.was_line)).toBeVisible();
    await expect(page.getByText(r.final_line)).toBeVisible();
    await expectNoSeriousAxeIssues(page);
  });

  test("S-06.states withdrawn, V-ACC.track/7: back in your drafts, Restore it, later stages not going ahead", async ({
    page,
  }) => {
    await openIdea(page, "T10");
    await expect(page.getByText("Withdrawn", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Withdrawn. It’s back in your drafts.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Restore it" })).toBeVisible();
    await expect(page.getByText("Withdrawn before review").first()).toBeAttached();
    await expect(page.getByText(", not going ahead").first()).toBeAttached();
    await expectNoSeriousAxeIssues(page);
  });

  test("L-MERGE.effects/1: a merged idea says where it went, with the note and a link that comes back to it", async ({
    page,
  }) => {
    const t11 = await openIdea(page, "T11");
    const r2 = await seededIdea("R2");
    await expect(page.getByText(`Merged into ${r2.ref} by the review desk.`)).toBeVisible();
    // Said once, in the card's sentence; the block under it has the note and the link
    await expect(page.getByText(new RegExp(`Merged into ${esc(r2.ref)}`))).toHaveCount(1);
    await expect(page.getByText(/^“.+”$/).first()).toBeVisible();
    await page.getByRole("link", { name: `Open ${r2.ref}` }).click();
    await page.waitForURL(new RegExp(`/ideas/${esc(r2.ref)}$`));
    await expect(page.getByRole("heading", { level: 1, name: r2.title })).toBeVisible();
    await page.getByRole("link", { name: `Back to ${t11.ref}` }).click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t11.ref)}$`));
  });

  test("S-09.layout, S-09.rules/1, J-BROWSE/5: a colleague's idea from the Wall shows the short summary only and goes back to the Wall", async ({
    page,
  }, info) => {
    const a1 = await openIdea(page, "A1", `?from=wall&back=${encodeURIComponent("/wall?sort=popular")}`);
    await expect(page.getByRole("heading", { level: 1, name: a1.title })).toBeVisible();
    const back = page.getByRole("link", { name: "Back to the Wall" });
    await expect(back).toHaveAttribute("href", "/wall?sort=popular");
    await expect(back).toContainText(isPhone(info.project.name) ? "Wall" : "Back to the Wall");
    await expect(page.getByText(/^Shared \w+day \d+ \w+ by /)).toBeVisible();
    await expect(
      page
        .getByText(
          isPhone(info.project.name)
            ? /^The short summary everyone sees\./
            : /^This is the short summary everyone at KFintech sees\./,
        )
        .filter({ visible: true }),
    ).toBeVisible();
    for (const name of ["Where it is", "About this idea", "Team up on this idea"]) {
      await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
    }
    await expect(page.getByText("Everyone at KFintech, as this short summary")).toBeVisible();
    // Nothing private (DEC-104): no words, answers, files, fix or reason
    for (const name of ["What you shared", "Your fix", "Attached", "You and the review desk"]) {
      await expect(page.getByRole("heading", { name })).toHaveCount(0);
    }
    await expect(page.getByText(/reason, as/)).toHaveCount(0);
    if (isPhone(info.project.name)) {
      // PhoneIdea: Team up comes before Where it is
      const team = await page.getByRole("heading", { level: 2, name: "Team up on this idea" }).boundingBox();
      const where = await page.getByRole("heading", { level: 2, name: "Where it is" }).boundingBox();
      expect(team!.y).toBeLessThan(where!.y);
    }
    await expectNoSeriousAxeIssues(page);
    await back.click();
    await page.waitForURL(/\/wall\?sort=popular$/);
  });

  test("S-09.states on the crew: You're on the crew with Say hello, from My ideas", async ({ page }) => {
    const r2 = await openIdea(
      page,
      "R2",
      `?from=my-ideas&back=${encodeURIComponent("/my-ideas?list=teamed")}`,
    );
    await expect(page.getByRole("link", { name: "Back to My ideas" })).toHaveAttribute(
      "href",
      "/my-ideas?list=teamed",
    );
    await expect(page.getByText("You’re on the crew. You’ll get its updates.")).toBeVisible();
    // The crew's way into the conversation (S-08), from the card (Idea.md "Say hello")
    await expect(
      page.getByRole("region", { name: "Team up on this idea" }).getByRole("link", { name: "Say hello" }),
    ).toHaveAttribute("href", `/ideas/${r2.ref}/conversation`);
    await expect(page.getByRole("button", { name: "Team up", exact: true })).toHaveCount(0);
    await expect(page.getByRole("img", { name: "Rekha Saxena" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);
  });

  test("S-09.states not asked, J-TEAMUP/1-2: a colleague opens the team-up sheet from Team up, and has no way into the conversation", async ({
    page,
  }) => {
    // Naveen is not on A1's crew and has not asked: the card offers Team up (C-SHEET-TEAMUP). Nothing is sent.
    const a1 = await seededIdea("A1");
    await signIn(page, CLUB.naveen);
    await page.goto(`/ideas/${a1.ref}`);
    await expect(page.getByRole("heading", { level: 1, name: a1.title })).toBeVisible();
    const card = page.getByRole("region", { name: "Team up on this idea" });
    // The conversation is for the sharer, crew, desk and committee only (P-PRODUCT.privacy, non-negotiable 7)
    await expect(card.getByRole("link", { name: "Say hello" })).toHaveCount(0);
    await expect(page.locator('.ip a[href$="/conversation"]')).toHaveCount(0);
    const teamUp = card.getByRole("button", { name: "Team up", exact: true });
    await teamUp.click();
    const sheet = page.getByRole("dialog", { name: "Team up with Aparna" });
    await expect(sheet).toBeVisible();
    await expect(sheet.getByRole("button", { name: "Send to Aparna" })).toBeVisible();
    // Escape closes it without sending, and focus is back on Team up (C-SHEET-TEAMUP.a11y, WCAG 2.4.3)
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    await expect(teamUp).toBeFocused();
    await expectNoSeriousAxeIssues(page);
  });

  test("S-06 from the Wall: the breadcrumb goes back to the Wall's own view", async ({ page }, info) => {
    await openIdea(page, "T5", `?from=wall&back=${encodeURIComponent("/wall?sort=popular&at=X&dy=120")}`);
    const link = isPhone(info.project.name)
      ? page.getByRole("link", { name: "Back to the Wall", exact: true })
      : page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Wall", exact: true });
    await expect(link).toHaveAttribute("href", "/wall?sort=popular&at=X&dy=120");
  });

  test("BLD-E021, P-ROUTES.state: the way back holds across a reload; a copied link and from=share do not carry it", async ({
    page,
    context,
  }, info) => {
    const phone = isPhone(info.project.name);
    const wayBack = (label: string) =>
      phone
        ? page.getByRole("link", {
            name: label === "Wall" ? "Back to the Wall" : `Back to ${label}`,
            exact: true,
          })
        : page
            .getByRole("navigation", { name: "Breadcrumb" })
            .getByRole("link", { name: label, exact: true });
    const t5 = await openIdea(page, "T5", `?from=wall&back=${encodeURIComponent("/wall?sort=popular")}`);
    await expect(wayBack("Wall")).toHaveAttribute("href", "/wall?sort=popular");
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeVisible();
    await expect(wayBack("Wall")).toHaveAttribute("href", "/wall?sort=popular");
    expect(here(page)).toBe(`/ideas/${t5.ref}`);

    // The copied link, opened in another tab, is the idea's own: the sharer's default way back
    const other = await context.newPage();
    await other.goto(`/ideas/${t5.ref}`);
    const otherWay = phone
      ? other.getByRole("link", { name: "Back to My ideas", exact: true })
      : other
          .getByRole("navigation", { name: "Breadcrumb" })
          .getByRole("link", { name: "My ideas", exact: true });
    await expect(otherWay).toHaveAttribute("href", "/my-ideas");
    await other.close();

    // The first arrival after sharing goes Home, once: a reload is not a first arrival
    await page.goto(`/ideas/${t5.ref}?from=share`);
    await soon.poll(() => here(page)).toBe(`/ideas/${t5.ref}`);
    await expect(wayBack("Home")).toHaveAttribute("href", "/home");
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeVisible();
    await expect(wayBack("My ideas")).toHaveAttribute("href", "/my-ideas");
  });

  test("S-06.rules/2, BLD-E021: after Withdraw, focus is on the idea's title, the status says so, and the way back holds", async ({
    page,
  }, info) => {
    // The seed is read, never changed: the withdraw call answers as the server would, and the page refreshes
    const t5 = await seededIdea("T5");
    await page.route(`**/api/ideas/${t5.ref}/withdraw`, (route) =>
      route.request().method() === "POST" ? route.fulfill({ json: {} }) : route.fallback(),
    );
    await openIdea(page, "T5", `?from=wall&back=${encodeURIComponent("/wall?sort=crew")}`);
    await page.getByRole("button", { name: "Withdraw" }).click();
    const form = page.getByRole("form", { name: "Withdraw this idea?" });
    await form.getByRole("button", { name: "Withdraw it" }).click();
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeFocused();
    await expect(
      page.getByRole("status").filter({ hasText: "Withdrawn. It’s back in your drafts." }),
    ).toBeAttached();
    const way = isPhone(info.project.name)
      ? page.getByRole("link", { name: "Back to the Wall", exact: true })
      : page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Wall", exact: true });
    await expect(way).toHaveAttribute("href", "/wall?sort=crew");
    expect(here(page)).toBe(`/ideas/${t5.ref}`);
  });

  test("V-ACC.visual/11: Read the full fix opens in a dialog; Escape closes it and focus returns", async ({
    page,
  }) => {
    await openIdea(page, "T5");
    const more = page.getByRole("button", { name: "Read the full fix" });
    await more.click();
    const dialog = page.getByRole("dialog", { name: "Your fix" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Close" })).toBeFocused();
    await expectNoSeriousAxeIssues(page);
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(more).toBeFocused();
  });

  test("S-06 keyboard: the way back, Edit, Withdraw, then the page in reading order", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the desktop board's order");
    await openIdea(page, "T5");
    await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link").focus();
    const seen: string[] = [];
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press("Tab");
      seen.push(
        await page.evaluate(
          () =>
            (document.activeElement as HTMLElement | null)?.innerText.trim() ||
            (document.activeElement?.getAttribute("aria-label") ?? ""),
        ),
      );
    }
    expect(seen.slice(0, 2), seen.join(" | ")).toEqual(["Edit it", "Withdraw"]);
  });

  test("S-06.rules/7, PhoneStatus: one column, the track runs down the page", async ({ page }, info) => {
    test.skip(!isPhone(info.project.name), "PhoneStatus");
    await page.setViewportSize({ width: 390, height: 844 });
    await openIdea(page, "T7");
    await expect(page.locator(".vtrk")).toBeVisible();
    await expect(page.locator(".trk")).toBeHidden();
    const shared = await page.getByRole("heading", { level: 2, name: "What you shared" }).boundingBox();
    const desk = await page.getByRole("heading", { level: 2, name: "You and the review desk" }).boundingBox();
    expect(shared!.y).toBeLessThan(desk!.y);
    await expectNoSeriousAxeIssues(page);
  });
});

test("an idea that does not exist is not found", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  const res = await page.goto("/ideas/IDEA-2099-999999");
  expect(res?.status()).toBe(404);
});
