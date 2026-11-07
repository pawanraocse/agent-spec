import fs from "fs";
import path from "path";
import zlib from "zlib";
import { fileURLToPath } from "url";

const BUDGET = 400 * 1024;
const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../bin/aspec_platform/ui/dist");

function walk(dir) {
  const out = [];
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) out.push(...walk(p));
    else if (/\.(js|css|html)$/.test(name)) out.push(p);
  }
  return out;
}

let total = 0;
for (const file of walk(dist)) {
  const raw = fs.readFileSync(file);
  const gz = zlib.gzipSync(raw, { level: 9 });
  total += gz.length;
}
if (total > BUDGET) {
  console.error(`UI gzip budget exceeded: ${total} bytes > ${BUDGET}`);
  process.exit(1);
}
console.log(`UI gzip budget OK: ${total} / ${BUDGET} bytes`);
