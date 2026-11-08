// Copies the shared personal-data patterns (services/worker/pii/patterns.yaml, the one source — BLD-005)
// into src/lib/pii/patterns.json so the browser and the server import the same data. Run: npm run sync:patterns
// tests/unit/patterns-sync.test.ts fails if the JSON drifts from the YAML.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(here, "../../../services/worker/pii/patterns.yaml");
const target = path.resolve(here, "../src/lib/pii/patterns.json");
const data = parse(readFileSync(source, "utf8"));
writeFileSync(target, JSON.stringify(data, null, 2) + "\n");
process.stdout.write(
  `patterns ${data.version}: ${data.patterns.length} patterns -> ${path.relative(process.cwd(), target)}\n`,
);
