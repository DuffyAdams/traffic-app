import { test, expect } from "@playwright/test";
import {
  capturePageErrors,
  gotoApp,
  resetMockData,
} from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("boots without console or request failures in the happy path", async ({ page }, testInfo) => {
  const errors = [];
  capturePageErrors(page, errors);

  await gotoApp(page);
  await expect(page.getByText("Created and Developed by")).toBeVisible();

  await testInfo.attach("runtime-errors.json", {
    body: JSON.stringify(errors, null, 2),
    contentType: "application/json",
  });

  expect(errors).toEqual([]);
});

test("holds together on mobile and desktop viewport sizes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoApp(page);

  const mobileWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(mobileWidth).toBeLessThanOrEqual(430);

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "SAN DIEGO WATCH" })).toBeVisible();

  const desktopWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(desktopWidth).toBeLessThanOrEqual(1460);
});
