/**
 * Live scan progress (§8, week 3): with `scan.live` on, the waiting screen listens to server-sent events instead
 * of polling and still reaches "Your summary is ready"; with it off (the default) it polls as on day one.
 * Desktop project only: the switch is shared, so two projects flipping it at once would race.
 */
import { expect, test, type Browser } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { PERSONAS, signIn } from "./helpers";

async function setLive(browser: Browser, state: "on" | "off") {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, PERSONAS.admin);
  await page.goto("/admin");
  const row = page.getByRole("row", { name: /scan\.live/ });
  const action = state === "on" ? "Switch on" : "Switch off";
  const toggle = row.getByRole("button", { name: `${action}: scan.live` });
  if (await toggle.isVisible()) {
    await toggle.click();
    await row.getByLabel("Reason for this change").fill(`e2e test: live progress ${state}`);
    await row.getByRole("button", { name: action, exact: true }).click();
    await expect(row.getByText(state === "on" ? "On" : "Off", { exact: true })).toBeVisible();
  }
  await ctx.close();
}

test("the waiting screen follows the scan over server-sent events", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "the switch is shared between projects");
  test.setTimeout(90_000);
  await setLive(browser, "on");
  try {
    const ctx = await browser.newContext();
    const a = await ctx.newPage();
    await signIn(a, PERSONAS.contributor);
    await a.goto("/share");
    await a.getByRole("button", { name: "Start a quick capture" }).click();
    await a.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    await a
      .getByLabel(QUESTIONS.quick_noticed.label)
      .fill(
        "Cheque deposit slips are typed twice at the branch counter, adding ten minutes to every deposit.",
      );
    await a
      .getByRole("group", { name: QUESTIONS.quick_who.label })
      .getByRole("checkbox", { name: "Investors" })
      .check();
    await a
      .getByRole("group", { name: new RegExp(QUESTIONS.quick_value.label) })
      .getByRole("radio", { name: "Not sure yet" })
      .check();
    for (const label of [/no investor or customer personal data/, /my own work/, /I accept the terms/]) {
      await a.getByRole("checkbox", { name: label }).check();
    }
    const stream = a.waitForResponse((r) => r.url().includes("/scan-events"), { timeout: 30_000 });
    await a.getByRole("button", { name: "Share your idea" }).click();
    await a.waitForURL(/\/done$/);
    const res = await stream;
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("text/event-stream");
    await expect(a.getByRole("heading", { level: 3, name: "Your summary is ready" })).toBeVisible({
      timeout: 20_000,
    });
    await ctx.close();
  } finally {
    await setLive(browser, "off");
  }
});
