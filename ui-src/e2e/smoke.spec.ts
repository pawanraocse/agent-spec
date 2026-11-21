import { expect, test } from "@playwright/test";

// DV-061: Live -> request -> inspector -> Coach -> Learning against fixture data.
test("live request, inspector, coach and learning", async ({ page }) => {
  await page.goto("/?token=e2e"); // the token is accepted on the index only; it sets the cookie
  await expect(page.getByRole("heading", { name: "Needs you" })).toBeVisible(); // Today, the landing page
  await page.goto("/requests");
  await expect(page.getByText("why does the login test fail").first()).toBeVisible();
  await expect(page.getByRole("tab", { name: /Orchestration/ })).toBeVisible();
  await page.getByRole("tab", { name: /Orchestration/ }).click(); // the request opens on Impact
  await expect(page.locator(".react-flow__node").first()).toBeVisible();

  // inspector from the waterfall: the subagent span shows its task and summary
  await page.getByRole("tab", { name: "Waterfall" }).click();
  await page.locator("button", { hasText: "agent-spec-search" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Find every caller of login()")).toBeVisible();
  await expect(dialog.getByText(/3 callers/)).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByRole("tab", { name: /Responses/ }).click();
  await expect(page.getByText(/session` is undefined when the token expires/)).toBeVisible();

  await page.getByRole("tab", { name: /Review/ }).click();
  await expect(page.getByText("Shell test run timed out")).toBeVisible();

  await page.getByRole("link", { name: "Impact" }).click();
  await page.getByRole("link", { name: "Coach" }).click();
  await expect(page.getByText("Top issues")).toBeVisible();
  await expect(page.getByText("Shell test run timed out").first()).toBeVisible();

  await page.getByRole("link", { name: "Learning" }).click();
  await expect(page.getByText("narrow test runs").first()).toBeVisible();
});

// PI-005/PI-006: the background index answers a question about a past request, and the
// request's Outcome tab shows measured signals.
test("ask the project, then open the request's outcome", async ({ page }) => {
  await page.goto("/?token=e2e");
  await page.getByRole("link", { name: "Ask" }).click();
  await page.getByLabel("Ask about this project").fill("login test fail");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Sources")).toBeVisible();
  await expect.poll(async () => page.getByText("Nothing matched").count(), { timeout: 10_000 }).toBe(0);
  const hit = page.getByRole("link", { name: /why does the login test fail/ }).first();
  await expect(hit).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy prompt for Cursor" })).toBeVisible();
  await hit.click();
  await page.getByRole("tab", { name: /Outcome/ }).click();
  await expect(page.getByText("Measured signals")).toBeVisible();
  await expect(page.getByText("Verified after last edit")).toBeVisible();
});
