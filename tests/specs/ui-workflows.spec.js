import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("loads the incident feed and supports source filtering", async ({ page }) => {
  await gotoApp(page);

  await expect(page.getByText("SIG Alert blocking two lanes near I-5 downtown.")).toBeVisible();
  await expect(page.getByText("Road closure due to police activity in Hillcrest.")).toBeVisible();

  const sourceResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/incidents") &&
      response.url().includes("source=SDPD") &&
      response.status() === 200,
  );

  await page.getByRole("button", { name: "SDPD" }).click();
  await sourceResponse;

  await expect(page.getByText("Road closure due to police activity in Hillcrest.")).toBeVisible();
  await expect(page.getByText("SIG Alert blocking two lanes near I-5 downtown.")).not.toBeVisible();
});

test("supports diagnostics, search, and comment submission", async ({ page }) => {
  await gotoApp(page);

  await page.getByRole("button", { name: /system diagnostics/i }).click();
  await expect(page.getByText("24-Hour Activity")).toBeVisible();
  await expect(page.getByText("Today")).toBeVisible();
  await expect(page.getByRole("button", { name: "Week" })).toBeVisible();

  await page.getByPlaceholder("Search incidents...").fill("North Park");
  await expect(page.getByText("Traffic accident with injuries near North Park.")).toBeVisible();
  await expect(page.getByText("Road closure due to police activity in Hillcrest.")).not.toBeVisible();

  const northParkCard = page.locator(".post").filter({
    hasText: "Traffic accident with injuries near North Park.",
  });
  await northParkCard.getByRole("button").nth(1).click();
  await page.getByPlaceholder("Write a comment...").fill("Detour confirmed.");
  await page.getByRole("button", { name: /send/i }).click();

  await expect(page.getByText("Comment added successfully!")).toBeVisible();
  await expect(page.getByText("Detour confirmed.")).toBeVisible();
});
