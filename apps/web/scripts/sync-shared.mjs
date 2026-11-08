// Copies shared YAML sources into JSON the web app imports (browser and server alike):
//   services/worker/pii/patterns.yaml -> src/lib/pii/patterns.json   (BLD-005, BLD-030)
//   policy/rbac.yaml                  -> src/lib/rbac.json           (BLD-040)
// Run `npm run sync:shared` after editing either source. Unit tests fail if a JSON copy drifts from its YAML.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../..");
const pairs = [
  ["services/worker/pii/patterns.yaml", "apps/web/src/lib/pii/patterns.json"],
  ["policy/rbac.yaml", "apps/web/src/lib/rbac.json"],
];
for (const [from, to] of pairs) {
  const data = parse(readFileSync(path.join(repo, from), "utf8"));
  writeFileSync(path.join(repo, to), JSON.stringify(data, null, 2) + "\n");
  process.stdout.write(`${from} -> ${to}\n`);
}
