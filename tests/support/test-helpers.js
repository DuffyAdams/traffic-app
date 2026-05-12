import { expect } from "@playwright/test";

export const apiBaseURL =
  process.env.PLAYWRIGHT_API_BASE_URL || "http://127.0.0.1:8787";

export async function resetMockData(request) {
  if (process.env.PLAYWRIGHT_USE_LIVE_BACKEND === "1") {
    return;
  }

  const response = await request.post(`${apiBaseURL}/__reset`);
  expect(response.ok()).toBeTruthy();
}

export async function gotoApp(page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "SAN DIEGO WATCH" })).toBeVisible();
  await expect(page.locator(".post, .empty-state").first()).toBeVisible({
    timeout: 12_000,
  });
}

export function capturePageErrors(page, errors) {
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(`console:${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    errors.push(`pageerror:${error.message}`);
  });
  page.on("requestfailed", (request) => {
    const errorText = request.failure()?.errorText || "unknown";
    if (errorText.includes("ERR_ABORTED")) {
      return;
    }
    errors.push(
      `requestfailed:${request.method()} ${request.url()} ${errorText}`,
    );
  });
}
