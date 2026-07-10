import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("keeps critical accessibility violations at zero on the main feed", async ({ page }, testInfo) => {
  await gotoApp(page);

  const results = await new AxeBuilder({ page }).analyze();
  const criticalViolations = results.violations.filter(
    (violation) => violation.impact === "critical",
  );

  await testInfo.attach("axe-results.json", {
    body: JSON.stringify(results, null, 2),
    contentType: "application/json",
  });

  expect(criticalViolations).toEqual([]);
});

test("supports keyboard access to search, diagnostics, and comments", async ({ page }) => {
  await gotoApp(page);

  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /accessibility mode/i })).toBeFocused();

  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /switch to/i })).toBeFocused();

  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /^stats$/i })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("24-Hour Activity")).toBeVisible();

  await page.keyboard.press("Enter");
  await expect(page.getByText("24-Hour Activity")).toBeHidden();

  const searchInput = page.getByPlaceholder("Search incidents...");
  for (let index = 0; index < 15; index += 1) {
    await page.keyboard.press("Tab");
    if (await searchInput.evaluate((input) => input === document.activeElement)) break;
  }
  await expect(searchInput).toBeFocused();
});
