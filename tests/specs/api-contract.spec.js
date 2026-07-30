import { test, expect } from "@playwright/test";
import { apiBaseURL, resetMockData } from "../support/test-helpers.js";

test.beforeEach(async ({ request }) => {
  await resetMockData(request);
});

test("lists incidents with filtering and cursor pagination", async ({ request }) => {
  const firstPage = await request.get(`${apiBaseURL}/api/incidents?limit=3&source=SDPD`);
  expect(firstPage.ok()).toBeTruthy();

  const incidents = await firstPage.json();
  expect(incidents).toHaveLength(3);
  expect(incidents.every((incident) => incident.source === "SDPD")).toBeTruthy();
  expect(new Date(incidents[0].timestamp).getTime()).toBeGreaterThanOrEqual(
    new Date(incidents[1].timestamp).getTime(),
  );

  const cursor = `${incidents[incidents.length - 1].timestamp}|${incidents[incidents.length - 1].incident_no}`;
  const secondPage = await request.get(
    `${apiBaseURL}/api/incidents?limit=3&source=SDPD&cursor=${encodeURIComponent(cursor)}`,
  );
  expect(secondPage.ok()).toBeTruthy();

  const nextIncidents = await secondPage.json();
  expect(nextIncidents.every((incident) => incident.source === "SDPD")).toBeTruthy();
  expect(nextIncidents.some((incident) => incident.incident_no === incidents[0].incident_no)).toBeFalsy();
});

test("returns stats in the frontend contract shape", async ({ request }) => {
  const response = await request.get(
    `${apiBaseURL}/api/incident_stats?date_filter=week&source=CHP`,
  );
  expect(response.ok()).toBeTruthy();

  const stats = await response.json();
  expect(stats).toMatchObject({
    eventsToday: expect.any(Number),
    eventsLastHour: expect.any(Number),
    eventsActive: expect.any(Number),
    totalIncidents: expect.any(Number),
    incidentsByType: expect.any(Object),
    topLocations: expect.any(Object),
    hourlyData: expect.any(Array),
    historicalCurrentHourAverage: expect.any(Number),
  });
  expect(stats.hourlyData).toHaveLength(7);
});

test("supports like and comment mutations with basic guardrails", async ({ request }) => {
  const incidentResponse = await request.get(
    `${apiBaseURL}/api/incidents?limit=1`,
  );
  expect(incidentResponse.ok()).toBeTruthy();
  const [incident] = await incidentResponse.json();
  const initialLikes = incident.likes;

  const likeResponse = await request.post(`${apiBaseURL}/api/incidents/A-1001/like`);
  expect(likeResponse.ok()).toBeTruthy();
  const likePayload = await likeResponse.json();
  expect(likePayload).toMatchObject({ likes: initialLikes + 1 });

  const duplicateLike = await request.post(`${apiBaseURL}/api/incidents/A-1001/like`);
  expect(duplicateLike.status()).toBe(400);

  const unlikeResponse = await request.delete(`${apiBaseURL}/api/incidents/A-1001/like`);
  expect(unlikeResponse.ok()).toBeTruthy();
  const unlikePayload = await unlikeResponse.json();
  expect(unlikePayload).toMatchObject({ likes: initialLikes });

  const emptyComment = await request.post(`${apiBaseURL}/api/incidents/A-1001/comment`, {
    data: { username: "Casey", comment: "" },
  });
  expect(emptyComment.status()).toBe(400);

  const validComment = await request.post(`${apiBaseURL}/api/incidents/A-1001/comment`, {
    data: {
      username: "Casey",
      comment: "Verified lane blockage.",
      timestamp: new Date().toISOString(),
    },
  });
  expect(validComment.ok()).toBeTruthy();

  const payload = await validComment.json();
  expect(payload.comments.at(-1)).toMatchObject({
    username: "Casey",
    comment: "Verified lane blockage.",
  });
});
