/**
 * Find the group proposal that holds these ideas. Matching by idea ID, not by the words in the summary: the
 * dev database keeps reviewed ideas from earlier runs, and a run may group them with this run's ideas, so the
 * proposal's description can come from an older idea. Leaves the page on the proposal.
 */
import { expect, type Page } from "@playwright/test";

export async function openProposalHolding(page: Page, ideaIds: string[], timeout = 90_000): Promise<void> {
  await expect(async () => {
    await page.goto("/review?type=cluster_proposal");
    const hrefs = await page
      .getByRole("link", { name: "Group proposal", exact: true })
      .evaluateAll((links) => links.map((a) => a.getAttribute("href") ?? ""));
    for (const href of hrefs.filter(Boolean)) {
      await page.goto(href);
      const found = await Promise.all(
        ideaIds.map((id) => page.getByRole("link", { name: id, exact: true }).count()),
      );
      if (found.every((n) => n > 0)) return;
    }
    throw new Error(`no open proposal holds ${ideaIds.join(" and ")} yet`);
  }).toPass({ timeout, intervals: [3_000] });
}

/**
 * Press "Run the grouping now" until the desk confirms a run. The route guard keeps its own 10-second switch
 * cache, so a click just after another spec switched `clusters.batch` back on can be refused: try again.
 */
export async function runGroupingNow(page: Page, timeout = 45_000): Promise<void> {
  await expect(async () => {
    await page.goto("/review");
    await page.getByRole("button", { name: "Run the grouping now" }).click({ timeout: 2_000 });
    await expect(page.getByRole("status").filter({ hasText: /run has started|already going/ })).toBeVisible({
      timeout: 3_000,
    });
  }).toPass({ timeout, intervals: [2_000] });
}
