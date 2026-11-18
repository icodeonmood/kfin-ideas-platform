/**
 * The real `channels()` (server/ways.ts) that S-03 Home and S-H3 read (DEC-105, BLD-A192, BLD-C183), over the real
 * kill-switch read and its fail-closed rule; only the database answer is faked. An unknown switch and a failed switch
 * read both leave email and Teams off, even with IT's addresses given. Synthetic addresses only.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let answer: { name: string; state: string }[] | Error = [];

vi.mock("@/server/db", () => ({
  getDb: () => ({
    selectFrom: () => ({
      select: () => ({
        execute: async () => {
          if (answer instanceof Error) throw answer;
          return answer;
        },
      }),
    }),
  }),
}));

const { channels } = await import("@/server/ways");
const { clearKillSwitchCache } = await import("@/server/killswitch");

describe("channels(): an unknown switch and a failed switch read are off (DEC-105, BLD-C183)", () => {
  beforeEach(() => {
    clearKillSwitchCache();
    vi.stubEnv("INTAKE_EMAIL_ADDRESS", "share@1pc.kfintech.example");
    vi.stubEnv("TEAMS_APP_LINK", "https://teams.example.test/l/app/1");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    clearKillSwitchCache();
  });

  it("the table knows neither intake switch: both off", async () => {
    answer = [{ name: "ai.all", state: "on" }];
    expect(await channels()).toMatchObject({ email: { on: false }, teams: { on: false } });
  });

  it("the switch read fails: both off, and channels() still answers", async () => {
    answer = new Error("the kill_switches table did not answer");
    expect(await channels()).toMatchObject({ email: { on: false }, teams: { on: false } });
  });

  it("both switches on, with the addresses given: both on (the same read)", async () => {
    answer = [
      { name: "intake.email", state: "on" },
      { name: "intake.teams", state: "on" },
    ];
    expect(await channels()).toMatchObject({
      email: { on: true, address: "share@1pc.kfintech.example" },
      teams: { on: true, link: "https://teams.example.test/l/app/1" },
    });
  });
});
