const now = new Date();

function isoHoursAgo(hoursAgo) {
  return new Date(now.getTime() - hoursAgo * 60 * 60 * 1000).toISOString();
}

function makeIncident(overrides) {
  return {
    incident_no: overrides.incident_no,
    timestamp: overrides.timestamp,
    description: overrides.description,
    location: overrides.location,
    neighborhood: overrides.neighborhood || "",
    map_filename: overrides.map_filename || "fixture-map.svg",
    likes: overrides.likes || 0,
    comments: overrides.comments || [],
    type: overrides.type || "Traffic Hazard",
    active: overrides.active ?? false,
    source: overrides.source || "CHP",
    severity: overrides.severity ?? null,
    Details: overrides.Details || [],
    latitude: overrides.latitude ?? 32.7157,
    longitude: overrides.longitude ?? -117.1611,
  };
}

const baseIncidents = [
  makeIncident({
    incident_no: "A-1001",
    timestamp: isoHoursAgo(0.2),
    description: "SIG Alert blocking two lanes near I-5 downtown.",
    location: "Downtown",
    neighborhood: "Core",
    likes: 0,
    comments: [],
    type: "SIG Alert",
    active: true,
    source: "CHP",
    severity: 5,
    Details: ["Unit en route", "Lanes 2 and 3 blocked"],
  }),
  makeIncident({
    incident_no: "A-1002",
    timestamp: isoHoursAgo(0.8),
    description: "Traffic accident with injuries near North Park.",
    location: "North Park",
    neighborhood: "North Park",
    likes: 1,
    comments: [{ username: "HarborFox", comment: "Heavy slowdown here.", timestamp: isoHoursAgo(0.7) }],
    type: "TRAFFIC ACCIDENT",
    active: true,
    source: "SDFD",
    severity: 4,
    Details: ["Medic requested"],
  }),
  makeIncident({
    incident_no: "A-1003",
    timestamp: isoHoursAgo(1.5),
    description: "Road closure due to police activity in Hillcrest.",
    location: "Hillcrest",
    neighborhood: "Hillcrest",
    type: "Road Closure",
    active: true,
    source: "SDPD",
    severity: 3,
  }),
  makeIncident({
    incident_no: "A-1004",
    timestamp: isoHoursAgo(2.2),
    description: "Vehicle debris reported on SR-163.",
    location: "Mission Valley",
    neighborhood: "Mission Valley",
    type: "Debris From Vehicle",
    active: false,
    source: "CHP",
    severity: 2,
  }),
  makeIncident({
    incident_no: "A-1005",
    timestamp: isoHoursAgo(3.5),
    description: "Wrong way driver reported near Chula Vista.",
    location: "Chula Vista",
    neighborhood: "South Bay",
    type: "Wrong Way Driver",
    active: true,
    source: "CHP",
    severity: 5,
  }),
  makeIncident({
    incident_no: "A-1006",
    timestamp: isoHoursAgo(4),
    description: "Structure fire response in La Jolla.",
    location: "La Jolla",
    neighborhood: "La Jolla",
    type: "STRUCTURE FIRE",
    active: true,
    source: "SDFD",
    severity: 5,
  }),
  makeIncident({
    incident_no: "A-1007",
    timestamp: isoHoursAgo(5.2),
    description: "Sheriff activity near El Cajon transit center.",
    location: "El Cajon",
    neighborhood: "East County",
    type: "DISTURBING PEACE",
    active: false,
    source: "SDSO",
    severity: 2,
  }),
  makeIncident({
    incident_no: "A-1008",
    timestamp: isoHoursAgo(6.5),
    description: "Traffic hazard from stalled vehicle in Pacific Beach.",
    location: "Pacific Beach",
    neighborhood: "Pacific Beach",
    type: "Traffic Hazard",
    active: false,
    source: "CHP",
    severity: 2,
  }),
  makeIncident({
    incident_no: "A-1009",
    timestamp: isoHoursAgo(8),
    description: "Auto theft investigation by SDPD in Clairemont.",
    location: "Clairemont",
    neighborhood: "Clairemont",
    type: "AUTO THEFT",
    active: false,
    source: "SDPD",
    severity: 3,
  }),
  makeIncident({
    incident_no: "A-1010",
    timestamp: isoHoursAgo(10),
    description: "Medical response assisting freeway collision.",
    location: "Mira Mesa",
    neighborhood: "Mira Mesa",
    type: "MEDICAL",
    active: false,
    source: "SDFD",
    severity: 3,
  }),
  makeIncident({
    incident_no: "A-1011",
    timestamp: isoHoursAgo(12),
    description: "Vandalism report holding traffic near Old Town.",
    location: "Old Town",
    neighborhood: "Old Town",
    type: "VANDALISM",
    active: false,
    source: "SDPD",
    severity: 1,
  }),
  makeIncident({
    incident_no: "A-1012",
    timestamp: isoHoursAgo(14),
    description: "Assist maintenance crew with lane closure.",
    location: "Sorrento Valley",
    neighborhood: "Sorrento Valley",
    type: "Assist CT with Maintenance",
    active: false,
    source: "CHP",
    severity: 1,
  }),
  makeIncident({
    incident_no: "A-1013",
    timestamp: isoHoursAgo(16),
    description: "Robbery investigation near Gaslamp Quarter.",
    location: "Gaslamp",
    neighborhood: "Gaslamp",
    type: "ROBBERY",
    active: false,
    source: "SDPD",
    severity: 4,
  }),
  makeIncident({
    incident_no: "A-1014",
    timestamp: isoHoursAgo(18),
    description: "Vegetation fire near Poway trailhead.",
    location: "Poway",
    neighborhood: "North Inland",
    type: "VEGETATION FIRE",
    active: false,
    source: "SDFD",
    severity: 4,
  }),
  makeIncident({
    incident_no: "A-1015",
    timestamp: isoHoursAgo(20),
    description: "Report of death investigation affecting local traffic.",
    location: "Encinitas",
    neighborhood: "North County",
    type: "REPORT OF DEATH",
    active: false,
    source: "SDSO",
    severity: 5,
  }),
  makeIncident({
    incident_no: "A-1016",
    timestamp: isoHoursAgo(22),
    description: "Spinout during rain near National City.",
    location: "National City",
    neighborhood: "South Bay",
    type: "SPINOUT",
    active: false,
    source: "CHP",
    severity: 2,
  }),
  makeIncident({
    incident_no: "A-1017",
    timestamp: isoHoursAgo(26),
    description: "Mental case response near Lakeside roadway.",
    location: "Lakeside",
    neighborhood: "East County",
    type: "MENTAL CASE",
    active: false,
    source: "SDSO",
    severity: 2,
  }),
  makeIncident({
    incident_no: "A-1018",
    timestamp: isoHoursAgo(36),
    description: "Construction slowdown near Del Mar.",
    location: "Del Mar",
    neighborhood: "North Coast",
    type: "Construction",
    active: false,
    source: "CHP",
    severity: 1,
  }),
];

function compareIncidentsDescending(a, b) {
  const ts = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  if (ts !== 0) return ts;
  return b.incident_no.localeCompare(a.incident_no);
}

function buildHourlyData(incidents) {
  const buckets = Array.from({ length: 24 }, () => 0);
  for (const incident of incidents) {
    const ageHours = Math.floor((now.getTime() - new Date(incident.timestamp).getTime()) / (60 * 60 * 1000));
    if (ageHours >= 0 && ageHours < 24) {
      buckets[23 - ageHours] += 1;
    }
  }
  return buckets;
}

function buildDayData(incidents, days) {
  const buckets = Array.from({ length: days }, () => 0);
  for (const incident of incidents) {
    const ageDays = Math.floor((now.getTime() - new Date(incident.timestamp).getTime()) / (24 * 60 * 60 * 1000));
    if (ageDays >= 0 && ageDays < days) {
      buckets[days - 1 - ageDays] += 1;
    }
  }
  return buckets;
}

function buildMonthData(incidents) {
  return buildDayData(incidents, 30);
}

function buildYearData(incidents) {
  const buckets = Array.from({ length: 12 }, () => 0);
  for (const incident of incidents) {
    const incidentDate = new Date(incident.timestamp);
    const monthDelta =
      now.getMonth() -
      incidentDate.getMonth() +
      (now.getFullYear() - incidentDate.getFullYear()) * 12;
    if (monthDelta >= 0 && monthDelta < 12) {
      buckets[11 - monthDelta] += 1;
    }
  }
  return buckets;
}

function filterByDate(incidents, dateFilter) {
  if (dateFilter === "week") {
    return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 7 * 24 * 60 * 60 * 1000);
  }
  if (dateFilter === "month") {
    return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 30 * 24 * 60 * 60 * 1000);
  }
  if (dateFilter === "year") {
    return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 365 * 24 * 60 * 60 * 1000);
  }
  return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 24 * 60 * 60 * 1000);
}

export function cloneIncident(incident) {
  return JSON.parse(JSON.stringify(incident));
}

export function seedIncidents() {
  return baseIncidents
    .map(cloneIncident)
    .sort(compareIncidentsDescending);
}

export function filterIncidents(incidents, query) {
  const limit = Number(query.get("limit") || "20");
  const cursor = query.get("cursor");
  const types = query.getAll("type");
  const locations = query.getAll("location");
  const sources = query.getAll("source");
  const activeOnly = query.get("active_only") === "true";

  let filtered = [...incidents];

  if (types.length > 0) {
    filtered = filtered.filter((incident) => types.includes(incident.type));
  }
  if (locations.length > 0) {
    filtered = filtered.filter((incident) => locations.includes(incident.location));
  }
  if (sources.length > 0) {
    filtered = filtered.filter((incident) => sources.includes(incident.source));
  }
  if (activeOnly) {
    filtered = filtered.filter((incident) => incident.active);
  }

  filtered.sort(compareIncidentsDescending);

  if (cursor) {
    const [cursorTimestamp, cursorIncidentNo] = cursor.split("|");
    filtered = filtered.filter((incident) => {
      if (incident.timestamp < cursorTimestamp) {
        return true;
      }
      if (incident.timestamp > cursorTimestamp) {
        return false;
      }
      return incident.incident_no < cursorIncidentNo;
    });
  }

  return filtered.slice(0, limit).map(cloneIncident);
}

export function buildStats(incidents, query) {
  const sources = query.getAll("source");
  const dateFilter = query.get("date_filter") || "day";

  let filtered = [...incidents];
  if (sources.length > 0) {
    filtered = filtered.filter((incident) => sources.includes(incident.source));
  }

  const dateScoped = filterByDate(filtered, dateFilter);
  const todayScoped = filterByDate(filtered, "day");
  const lastHourThreshold = now.getTime() - 60 * 60 * 1000;
  const eventsLastHour = filtered.filter(
    (incident) => new Date(incident.timestamp).getTime() >= lastHourThreshold,
  ).length;

  const incidentsByType = {};
  const topLocations = {};
  for (const incident of dateScoped) {
    incidentsByType[incident.type] = (incidentsByType[incident.type] || 0) + 1;
    if (incident.location) {
      topLocations[incident.location] = (topLocations[incident.location] || 0) + 1;
    }
  }

  let hourlyData;
  if (dateFilter === "year") {
    hourlyData = buildYearData(filtered);
  } else if (dateFilter === "month") {
    hourlyData = buildMonthData(filtered);
  } else if (dateFilter === "week") {
    hourlyData = buildDayData(filtered, 7);
  } else {
    hourlyData = buildHourlyData(filtered);
  }

  return {
    eventsToday: todayScoped.length,
    eventsLastHour,
    eventsActive: filtered.filter((incident) => incident.active).length,
    totalIncidents: dateScoped.length,
    incidentsByType,
    topLocations,
    hourlyData,
    historicalCurrentHourAverage: 2,
    generatedAt: new Date().toISOString(),
  };
}
