// CP-002 / DV-062: the initial bundle (everything index.html loads eagerly) must stay under
// 400 KB gzip. Lazy chunks (orchestration graph, knowledge graph) load on demand and are
// reported separately, per dashboard_overhaul.md §14.5.
import fs from "fs";
import path from "path";
import zlib from "zlib";
import { fileURLToPath } from "url";

const BUDGET = 400 * 1024;
const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../bin/aspec_platform/ui/dist");
const gz = (p) => zlib.gzipSync(fs.readFileSync(p), { level: 9 }).length;

const index = fs.readFileSync(path.join(dist, "index.html"), "utf8");
const initial = new Set(["index.html"]);
for (const m of index.matchAll(/(?:src|href)="\/?([^"]+\.(?:js|css))"/g)) initial.add(m[1]);

let eager = 0;
let lazy = 0;
const walk = (dir) => fs.readdirSync(dir).flatMap((n) => {
  const p = path.join(dir, n);
  return fs.statSync(p).isDirectory() ? walk(p) : [p];
});
for (const file of walk(dist)) {
  if (!/\.(js|css|html)$/.test(file)) continue;
  const rel = path.relative(dist, file).split(path.sep).join("/");
  if (initial.has(rel)) eager += gz(file);
  else lazy += gz(file);
}
if (eager > BUDGET) {
  console.error(`UI gzip budget exceeded: initial ${eager} bytes > ${BUDGET}`);
  process.exit(1);
}
console.log(`UI gzip budget OK: initial ${eager} / ${BUDGET} bytes; lazy chunks ${lazy} bytes`);
