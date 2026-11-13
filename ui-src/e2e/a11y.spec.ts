import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// DV-062: no serious or critical WCAG 2 A/AA violations on the v3 spaces, in both themes.
for (const theme of ["dark", "light"]) {
  for (const path of ["/", "/coach", "/learning"]) {
    test(`a11y ${theme} ${path}`, async ({ page }) => {
      await page.goto("/?token=e2e");
      await page.evaluate((t) => localStorage.setItem("aspec-theme", t), theme);
      await page.goto(path);
      await page.waitForTimeout(1200);
      const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).exclude(".react-flow").analyze();
      const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    });
  }
}
