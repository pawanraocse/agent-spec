import { expect, test } from "@playwright/test";

// DV-061: Live -> request -> inspector -> Coach -> Learning against fixture data.
test("live request, inspector, coach and learning", async ({ page }) => {
  await page.goto("/?token=e2e");
  await expect(page.getByText("why does the login test fail").first()).toBeVisible();
  await expect(page.getByRole("tab", { name: /Orchestration/ })).toBeVisible();
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

  await page.getByRole("link", { name: "Coach" }).click();
  await expect(page.getByText("Top issues")).toBeVisible();
  await expect(page.getByText("Shell test run timed out").first()).toBeVisible();

  await page.getByRole("link", { name: "Learning" }).click();
  await expect(page.getByText("narrow test runs").first()).toBeVisible();
});
