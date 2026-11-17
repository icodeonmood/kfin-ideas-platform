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
    await expect(page.getByText("We’ll tell you on Teams and by email when anything changes.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit it" })).toHaveAttribute(
      "href",
      `/ideas/${t5.ref}/edit`,
    );
    await expect(page.getByRole("button", { name: "Withdraw" })).toBeVisible();
    await expect(
      page.getByText(
        /^Open to changes until \w+day \d+ \w+\. Edit or withdraw it any time before the review desk/,
      ),
    ).toBeVisible();
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

  test("S-06.states questions, V-ACC.track/3: the questions card with its countdown and Answer the questions; the window has closed", async ({
    page,
  }) => {
    const t6 = await openIdea(page, "T6");
    await expect(page.getByText("Needs you", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Harish has 3 questions for you" })).toBeVisible();
    await expect(page.getByText("Answer goes to").first()).toBeVisible();
    await expect(page.getByText(/^\d+ days? left to answer$|left to answer/).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Answer the questions" })).toHaveAttribute(
      "href",
      `/ideas/${t6.ref}/answer`,
    );
    await expect(
      page.getByText(
        /^The review desk opened it on \w+day \d+ \w+, so the idea itself can’t be changed now\./,
      ),
    ).toBeVisible();
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
    await expect(page.getByText(`Merged into ${r2.ref} by the review desk`)).toBeVisible();
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
    await expect(page.getByRole("link", { name: "Say hello" })).toHaveAttribute(
      "href",
      `/ideas/${r2.ref}/conversation`,
    );
    await expect(page.getByRole("img", { name: "Rekha Saxena" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);
  });

  test("S-06 from the Wall: the breadcrumb goes back to the Wall's own view", async ({ page }, info) => {
    await openIdea(page, "T5", `?from=wall&back=${encodeURIComponent("/wall?sort=popular&at=X&dy=120")}`);
    const link = isPhone(info.project.name)
      ? page.getByRole("link", { name: "Back to the Wall", exact: true })
      : page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Wall", exact: true });
    await expect(link).toHaveAttribute("href", "/wall?sort=popular&at=X&dy=120");
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
