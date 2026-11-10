/**
 * Live scan progress (§8, week 3): with `scan.live` on, the waiting screen listens to server-sent events instead
 * of polling and still reaches "Your summary is ready"; with it off it polls. On from day one (DEC-088).
 * Desktop project only: the switch is shared, so two projects flipping it at once would race.
 */
import { expect, test } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { PERSONAS, setSwitch, signIn } from "./helpers";

test("the waiting screen follows the scan over server-sent events", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "the switch is shared between projects");
  test.setTimeout(90_000);
  const before = await setSwitch(browser, "scan.live", "on");
  try {
    const ctx = await browser.newContext();
    const a = await ctx.newPage();
    await signIn(a, PERSONAS.contributor);
    // The route guard keeps its own 10-second switch cache: wait until it lets the stream through (an unknown
    // submission then answers 404, not the switch's 503).
    await expect
      .poll(
        async () =>
          (await a.request.get("/api/submissions/00000000-0000-4000-8000-000000000000/scan-events")).status(),
        { timeout: 20_000, intervals: [1_000] },
      )
      .not.toBe(503);
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
    await setSwitch(browser, "scan.live", before); // as we found it (DEC-088)
  }
});
