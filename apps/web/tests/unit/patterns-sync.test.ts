import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import json from "@/lib/pii/patterns.json";

describe("shared pattern file (BLD-005)", () => {
  it("patterns.json matches services/worker/pii/patterns.yaml exactly; run `npm run sync:patterns`", () => {
    const yaml = parse(
      readFileSync(path.resolve(__dirname, "../../../../services/worker/pii/patterns.yaml"), "utf8"),
    );
    expect(json).toEqual(yaml);
  });
});
