---
name: agent-spec-webapp-testing
description: >-
  Toolkit for testing local web applications using Playwright. Verifies frontend
  functionality, debugs UI behaviour, captures screenshots and browser logs.
  Runs inside the agent-spec SDLC — requires gate 7 (agent-spec-testing) to be open.
---

# Web Application Testing

## Gate (check this first)

```bash
./.agent-spec/bin/agent-spec-gate.py check 7
```

`BLOCKED` → stop. Run `/agent-spec-testing` first to open the gate.

Adopt the **@QA** persona (`.agent-spec/personas/QA.md`) before proceeding.

## Which skill to use

| Situation | Use |
|---|---|
| Running the backend test suite (unit, integration, contract) | `/agent-spec-testing` |
| Verifying UI behaviour, selectors, or page flows in a browser | **this skill** |
| Both | Run `/agent-spec-testing` first (it opens gate 7), then this skill |

Do not use this skill to run `pytest`, `jest`, or any non-browser test runner.

---

To test local web applications, write native Python Playwright scripts.

**Helper Scripts Available**:
- `scripts/with_server.py` — Manages server lifecycle (supports multiple servers)

**Always run scripts with `--help` first** to see usage. DO NOT read the source until you
try running the script first and find that a customised solution is absolutely necessary.
These scripts can be very large and thus pollute your context window. They exist to be
called directly as black-box scripts rather than ingested into your context window.

## Decision Tree: Choosing Your Approach

```
User task → Is it static HTML?
    ├─ Yes → Read HTML file directly to identify selectors
    │         ├─ Success → Write Playwright script using selectors
    │         └─ Fails/Incomplete → Treat as dynamic (below)
    │
    └─ No (dynamic webapp) → Is the server already running?
        ├─ No → Run: python scripts/with_server.py --help
        │        Then use the helper + write simplified Playwright script
        │
        └─ Yes → Reconnaissance-then-action:
            1. Navigate and wait for networkidle
            2. Take screenshot or inspect DOM
            3. Identify selectors from rendered state
            4. Execute actions with discovered selectors
```

## Example: Using with_server.py

**Single server:**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py
```

**Multiple servers (e.g., backend + frontend):**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python your_automation.py
```

Automation script — include only Playwright logic (servers are managed automatically):
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)  # Always headless
    page = browser.new_page()
    page.goto('http://localhost:5173')
    page.wait_for_load_state('networkidle')  # CRITICAL: wait for JS to execute
    # ... your automation logic
    browser.close()
```

## Reconnaissance-Then-Action Pattern

1. **Inspect rendered DOM**:
   ```python
   page.screenshot(path='/tmp/inspect.png', full_page=True)
   content = page.content()
   page.locator('button').all()
   ```
2. **Identify selectors** from inspection results
3. **Execute actions** using discovered selectors

❌ Don't inspect the DOM before `networkidle` on dynamic apps.
✅ Do `page.wait_for_load_state('networkidle')` before any inspection.

## Best Practices

- Use bundled scripts as black boxes — `--help` then invoke directly.
- Use `sync_playwright()` for synchronous scripts.
- Always close the browser when done.
- Prefer `text=`, `role=`, or ID selectors over fragile CSS paths.
- Add explicit waits: `page.wait_for_selector()` before acting on dynamic elements.

## Reference Files

- `examples/element_discovery.py` — discovering buttons, links, inputs
- `examples/static_html_automation.py` — using `file://` URLs for local HTML
- `examples/console_logging.py` — capturing console logs during automation