import { afterEach, describe, expect, it } from "vitest";

import { appBaseUrl, isProductionLike, oidcConfig } from "@/server/config";

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
      APP_BASE_URL: "https://ideas.kfintech.example",
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

  it("needs APP_BASE_URL outside dev, so the launch QR never points at localhost (review A1)", () => {
    process.env.APP_ENV = "uat";
    delete process.env.APP_BASE_URL;
    expect(() => appBaseUrl()).toThrow(/APP_BASE_URL is not set/);
    process.env.APP_BASE_URL = "https://ideas.kfintech.example/";
    expect(appBaseUrl().host).toBe("ideas.kfintech.example");
    process.env.APP_ENV = "dev";
    delete process.env.APP_BASE_URL;
    expect(appBaseUrl().toString()).toBe("http://localhost:3000/");
  });
});
