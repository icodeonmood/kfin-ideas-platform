import { afterEach, describe, expect, it } from "vitest";

import { isProductionLike, oidcConfig } from "@/server/config";

describe("settings fail closed (B2 review)", () => {
  const saved = { ...process.env };
  afterEach(() => {
    process.env = { ...saved };
  });

  it("treats a missing or unknown APP_ENV as production", () => {
    delete process.env.APP_ENV;
    expect(isProductionLike()).toBe(true);
    process.env.APP_ENV = "staging";
    expect(isProductionLike()).toBe(true);
    process.env.APP_ENV = "dev";
    expect(isProductionLike()).toBe(false);
  });

  it("refuses the mock IdP and the dev-only internal IdP address outside dev", () => {
    Object.assign(process.env, {
      APP_ENV: "prod",
      OIDC_MODE: "entra",
      OIDC_ISSUER: "https://login.example/tenant/v2.0",
      OIDC_CLIENT_ID: "ideas",
    });
    process.env.OIDC_INTERNAL_BASE = "http://mock-oidc:8080";
    expect(() => oidcConfig()).toThrow(/dev-only/);
    delete process.env.OIDC_INTERNAL_BASE;
    expect(oidcConfig().mode).toBe("entra");
    process.env.OIDC_MODE = "mock";
    expect(() => oidcConfig()).toThrow(/not allowed/);
    delete process.env.OIDC_MODE;
    expect(() => oidcConfig()).toThrow(/OIDC_MODE is not set/);
  });
});
