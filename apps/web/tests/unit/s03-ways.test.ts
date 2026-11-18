/**
 * S-03 Home's page (BLD-C183): section 4's ways in read the server's `intake.email` and `intake.teams` switches
 * through `channels()`, the read S-H3 uses (BLD-A192). A failed read counts as both off. Synthetic data only.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Channels } from "@/server/ways";

let ways: Channels | Error;

vi.mock("next/headers", () => ({ headers: async () => new Headers() }));
vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    throw new Error(`redirect ${to}`);
  },
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("@/server/auth/current", () => ({
  currentUser: async () => ({ id: "00000000-0000-4000-8000-0000000000a1", name: "Kavya Rao" }),
}));
vi.mock("@/server/home", () => ({ firstHomeVisit: async () => false }));
vi.mock("@/server/ways", () => ({
  channels: async () => {
    if (ways instanceof Error) throw ways;
    return ways;
  },
}));

const { default: Home } = await import("@/app/home/page");

const open = (email: boolean, teams: boolean): Channels => ({
  email: { on: email, address: "share@1pc.kfintech.example" },
  teams: { on: teams, link: "https://teams.example.test/l/app/1" },
});

async function props() {
  const el = (await Home()) as {
    props: { waysOn: { email: boolean; teams: boolean }; outlookAddress: string | null };
  };
  return el.props;
}

describe("S-03.sections/4 page: the switches come from the server (DEC-105, BLD-A192, BLD-C183)", () => {
  beforeEach(() => {
    ways = open(false, false);
  });

  it("both off", async () => {
    expect(await props()).toMatchObject({ waysOn: { email: false, teams: false }, outlookAddress: null });
  });

  it("both on", async () => {
    ways = open(true, true);
    expect(await props()).toMatchObject({
      waysOn: { email: true, teams: true },
      outlookAddress: "share@1pc.kfintech.example",
    });
  });

  it("one of each", async () => {
    ways = open(true, false);
    expect((await props()).waysOn).toEqual({ email: true, teams: false });
    ways = open(false, true);
    expect(await props()).toMatchObject({ waysOn: { email: false, teams: true }, outlookAddress: null });
  });

  it("a failed read counts as both off", async () => {
    ways = new Error("the switch table did not answer");
    expect(await props()).toMatchObject({ waysOn: { email: false, teams: false }, outlookAddress: null });
  });
});
