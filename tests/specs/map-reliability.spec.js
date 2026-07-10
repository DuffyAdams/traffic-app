import { test, expect } from "@playwright/test";
import { gotoApp, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("map tiles load and the canvas recovers after the tab is hidden", async ({ page }) => {
  const runtimeErrors = [];
  const tileStatuses = [];

  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") runtimeErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().includes("/map_tiles/sandiego.pmtiles")) {
      tileStatuses.push(response.status());
    }
  });

  await gotoApp(page);
  const mapTab = page.getByRole("button", { name: /^map$/i });
  await mapTab.click();

  const canvas = page.locator(".maplibregl-canvas").last();
  await expect(canvas).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".map-status")).toBeHidden({ timeout: 20_000 });
  await expect.poll(() => tileStatuses.includes(206)).toBeTruthy();

  const initialSize = await canvas.evaluate((element) => ({
    width: element.width,
    height: element.height,
  }));
  expect(initialSize.width).toBeGreaterThan(0);
  expect(initialSize.height).toBeGreaterThan(0);

  await page.locator(".source-tab").first().click();
  await mapTab.click();
  await expect(canvas).toBeVisible();

  await expect.poll(async () => canvas.evaluate((element) => ({
    width: element.width,
    height: element.height,
  }))).toEqual(initialSize);

  expect(runtimeErrors).toEqual([]);
});
