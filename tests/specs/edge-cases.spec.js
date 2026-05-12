import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("shows an empty search state for non-matching queries", async ({ page }) => {
  await gotoApp(page);

  await page.getByPlaceholder("Search incidents...").fill("no-match-expected");
  await expect(page.getByText("No incidents match your search.")).toBeVisible();
  await expect(page.getByText("Try adjusting your query or loading more posts.")).toBeVisible();
});

test("falls back gracefully when the incident feed request fails", async ({ page }) => {
  await page.route("**/api/incidents?*", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: "forced failure" }),
    });
  });

  await page.goto("/");

  await expect(page.getByText("Unable to load incidents at this time.")).toBeVisible();
  await expect(
    page.getByText("Failed to load incidents. Please check your connection and try again."),
  ).toBeVisible();
});
