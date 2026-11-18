/**
 * BLD-A224, S-02 (J-RECOVER/1): a setting left empty with a note after it (`KEY=   # note`) reaches the app as the
 * note's text when Docker Compose reads the env file. The web app treats such a value as unset, as the worker does,
 * so S-02's help line leaves the extension out instead of showing the note.
 */
import { afterEach, describe, expect, it } from "vitest";

import { envText, itServiceDeskExtension } from "@/server/config";

const KEY = "IT_SERVICE_DESK_EXTENSION";
const before = process.env[KEY];

afterEach(() => {
  if (before === undefined) delete process.env[KEY];
  else process.env[KEY] = before;
});

describe("BLD-A224 envText: a comment is not a value", () => {
  it("S-02: unset, empty or blank leaves the extension out", () => {
    delete process.env[KEY];
    expect(itServiceDeskExtension()).toBeNull();
    process.env[KEY] = "";
    expect(itServiceDeskExtension()).toBeNull();
    process.env[KEY] = "   ";
    expect(itServiceDeskExtension()).toBeNull();
  });

  it("S-02, J-RECOVER/1: a value that is the env file's note counts as unset", () => {
    process.env[KEY] = "# S-02 help lines; IT gives the number (P-DECISIONS.signoff/5). Empty: left out";
    expect(itServiceDeskExtension()).toBeNull();
    process.env[KEY] = "   #note";
    expect(envText(KEY)).toBeNull();
  });

  it("a real extension is kept, trimmed", () => {
    process.env[KEY] = " 4455 ";
    expect(itServiceDeskExtension()).toBe("4455");
    process.env[KEY] = "040-4455 ext 12";
    expect(envText(KEY)).toBe("040-4455 ext 12");
  });
});
