import { defineConfig } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// DV-061 smoke: the real stdlib server on a fixture project built by e2e/make-fixture.py.
const project = path.resolve(__dirname, "e2e/.fixture-project");
const repo = path.resolve(__dirname, "..");

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8797",
    launchOptions: process.env.CHROME ? { executablePath: process.env.CHROME } : {},
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: `python3 ${repo}/ui-src/e2e/make-fixture.py ${project} && AGENT_SPEC_TOKEN=e2e AGENT_SPEC_CURSOR_STORE=0 AGENT_SPEC_DB=${project}/p.db python3 ${repo}/bin/agent-spec-platform.py serve --project ${project} --port 8797`,
    url: "http://127.0.0.1:8797/?token=e2e",
    reuseExistingServer: false,
    timeout: 20_000,
  },
});
