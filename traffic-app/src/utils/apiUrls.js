export function buildIncidentsUrl({
  limit,
  cursor,
  types = [],
  locations = [],
  activeOnly = false,
  source = "all",
}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  for (const type of types) params.append("type", type);
  for (const location of locations) params.append("location", location);
  if (activeOnly) params.set("active_only", "true");
  if (source && source !== "all" && source !== "map") {
    params.set("source", source);
  }
  return `/api/incidents?${params.toString()}`;
}

export function buildStatsUrl(timeFilter, source = "all") {
  const params = new URLSearchParams({ date_filter: timeFilter });
  if (source && source !== "all" && source !== "map") {
    params.set("source", source);
  }
  return `/api/incident_stats?${params.toString()}`;
}
