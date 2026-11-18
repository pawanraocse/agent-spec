// Record the H-051 fallback video: the demo.md story, end to end, against a built demo.
//
// Terminal beats run their command live while recording and show its real output; dashboard
// beats are clicks in a real browser. Nothing is mocked.
//
//   bash examples/mesh-demo/demo-setup.sh /tmp/agent-spec-demo
//   (cd /tmp/agent-spec-demo/orders-api && AGENT_SPEC_TOKEN=demo python3 .agent-spec/bin/agent-spec-platform.py serve --port 8791) &
//   cd ui-src && node ../examples/mesh-demo/record-video.mjs /tmp/agent-spec-demo/orders-api http://127.0.0.1:8791 demo out-dir
//
// Needs Playwright (ui-src devDependency). Writes <out-dir>/*.webm; convert with ffmpeg.
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// Resolve Playwright from the directory the script is run in (ui-src), not from this file's.
const { chromium } = createRequire(path.join(process.cwd(), "noop.js"))("playwright");

const [hub, base, token, outDir] = process.argv.slice(2);
if (!outDir) throw new Error("usage: record-video.mjs <hub> <dashboard-url> <token> <out-dir>");
const SIZE = { width: 1280, height: 760 };
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const sh = (cmd) => {
  try { return execSync(cmd, { cwd: hub, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 60000 }); }
  catch (e) { return (e.stdout || "") + (e.stderr || ""); }
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: SIZE, recordVideo: { dir: outDir, size: SIZE }, acceptDownloads: true });
const page = await ctx.newPage();
const wait = (s) => page.waitForTimeout(s * 1000);

const CARD_CSS = `body{margin:0;background:#0d1117;color:#e6edf3;font:15px/1.45 ui-monospace,Menlo,Consolas,monospace}
  .cap{background:#161b22;border-bottom:1px solid #30363d;padding:14px 28px;font:600 18px system-ui,sans-serif}
  .cap small{font-weight:400;color:#8b949e;margin-left:10px}
  pre{margin:0;padding:18px 28px;white-space:pre-wrap;word-break:break-word}
  .p{color:#7ee787}.c{color:#79c0ff}`;

/** A terminal card: caption, then each command typed and its live output. */
async function terminal(caption, note, cmds, hold = 7) {
  const blocks = cmds.map((c) => `<span class="p">orders-api $</span> <span class="c">${esc(c)}</span>\n${esc(sh(c).trimEnd())}\n`);
  await page.setContent(`<style>${CARD_CSS}</style><div class="cap">${esc(caption)}<small>${esc(note)}</small></div><pre>${blocks.join("\n")}</pre>`);
  await wait(hold);
}

/** A caption bar laid over the dashboard, so the beat is named on screen. */
async function caption(text, note) {
  await page.evaluate(([t, n]) => {
    document.getElementById("demo-cap")?.remove();
    const d = document.createElement("div");
    d.id = "demo-cap";
    d.style.cssText = "position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;background:#0d1117ee;color:#fff;padding:10px 18px;border-radius:8px;font:600 15px system-ui,sans-serif;box-shadow:0 4px 18px #0006;max-width:90%";
    d.innerHTML = t + (n ? `<span style="font-weight:400;color:#c9d1d9;margin-left:10px">${n}</span>` : "");
    document.body.appendChild(d);
  }, [text, note || ""]);
}
const go = async (p) => { await page.goto(base + p); await wait(1.5); };

// 0. Title
await page.setContent(`<style>${CARD_CSS} .t{display:flex;flex-direction:column;justify-content:center;height:100vh;padding:0 80px;font-family:system-ui,sans-serif}
  h1{font-size:40px;margin:0 0 12px}p{color:#8b949e;font-size:18px;margin:4px 0}</style>
  <div class="t"><h1>algosec-agent-spec — the 5-minute demo</h1><p>Recorded fallback for demo.md. Four repos, offline, network off.</p>
  <p>Terminal output is produced live during the recording; the dashboard is driven in a real browser.</p></div>`);
await wait(4);

// 1. Install
await terminal("0:00 Install", "the harness is plain files in the repo: hooks, rules, stdlib Python",
  ["ls .cursor/hooks", "ls .agent-spec/bin | head -12"], 6);
// 2. Digest
await terminal("0:30 Digest", "the block every new chat starts with, in place of opening four files",
  ["python3 .agent-spec/bin/agent-spec-digest.py"], 8);
// 3. Cross-repo blast radius and recall
await terminal("1:00 Cross-repo blast radius", "shop-ui calls this file; a fix recorded in another repo comes back with its citation",
  ["python3 .agent-spec/bin/graphify-mesh.py query --file orders-api:orders_api/routes.py",
   'python3 .agent-spec/bin/agent-spec-recall.py "worker processes orders.created twice"'], 10);

// 4. Tier-3 edit blocked
await page.goto(base + "/?token=" + encodeURIComponent(token));
await wait(1.5);
await go("/risk");
await caption("1:45 Tier-3 edit blocked", "routes.py is called from another repo, so the agent's edit waits here");
await wait(6);
// 5. Approved in the dashboard
await caption("2:30 Approved in the dashboard", "one retry within 30 minutes; the decision is a row in metrics/risk.jsonl");
await wait(1.5);
await page.getByRole("button", { name: "Approve once" }).first().click();
await wait(4);

// 6. Impact of the recorded chat
await go("/chats");
await caption("3:00 Impact", "the recorded Cursor chat, replayed through the real hooks");
await wait(2);
await page.getByRole("button", { name: /hook-probe collect/ }).first().click();
await wait(2);
await page.getByRole("button", { name: /tools ·/ }).last().click();
await wait(2);
const impact = page.getByRole("tab", { name: /Impact/ });
if (await impact.count()) await impact.first().click();
await caption("3:00 Impact", "every figure carries its badge; this chat read no files, so it kept 0 tokens out");
await wait(7);
await page.mouse.move(900, 450);
await page.mouse.wheel(0, 600);
await caption("3:00 Impact", "the raw-code-full rules it held, and the fact the digest injected (measured)");
await wait(6);

// 7. Learning proposal approved
await go("/proposals");
await caption("3:45 Learning proposal approved", "the fact moves into memory and is audited in metrics/proposals.jsonl");
await wait(5);
await page.getByRole("button", { name: "Approve" }).first().click();
await wait(3);
await terminal("3:45 Next chat's digest carries it", "the approved fact is now in what a new chat receives",
  ["python3 .agent-spec/bin/agent-spec-digest.py"], 8);

// 8. Audit export, then verify and tamper
await go("/chats");
await caption("4:15 Audit export", "redacted JSONL of requests, tool actions, risk decisions; hash-chained");
await page.getByRole("button", { name: /Rename GET/ }).first().click();
await wait(2);
const [dl] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Export audit/ }).first().click()]);
const file = path.join(hub, "audit-export.jsonl");
await dl.saveAs(file);
await wait(3);
const lines = fs.readFileSync(file, "utf8").split("\n");
// Tamper with line 2 the way someone hiding a decision would: change one value, keep valid JSON.
const row = JSON.parse(lines[1]);
const key = Object.keys(row).find((k) => typeof row[k] === "string" && !/hash|prev/i.test(k));
row[key] = row[key] + " (edited)";
lines[1] = JSON.stringify(row);
fs.writeFileSync(path.join(hub, "audit-edited.jsonl"), lines.join("\n"));
await terminal("4:15 Verify the export", "--verify names the first line that was edited",
  ["wc -l audit-export.jsonl", "python3 .agent-spec/bin/agent-spec-platform.py audit --verify audit-export.jsonl",
   "python3 .agent-spec/bin/agent-spec-platform.py audit --verify audit-edited.jsonl"], 9);

await page.close();
await ctx.close();
await browser.close();
console.log("recorded to", outDir);
