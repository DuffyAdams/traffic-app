<script>
    import { onMount, onDestroy, mount, unmount } from "svelte";
    import maplibregl from "maplibre-gl";
    import * as pmtiles from "pmtiles";
    import "maplibre-gl/dist/maplibre-gl.css";

    import IncidentMarker from "./IncidentMarker.svelte";
    import { formatTimestamp } from "../utils/helpers.js";

    // We no longer rely on the parent's paginated feed.
    // MapTab fetches its own complete dataset.
    let allIncidents = [];

    let mapContainer;
    let map;
    let markers = {}; // Store marker references by ID
    let refreshInterval;

    let showCHP = true;
    let showSDPD = true;
    let showSDFD = true;
    let showInactive = true;

    function toggleFilter(source) {
        if (source === "CHP") showCHP = !showCHP;
        else if (source === "SDPD") showSDPD = !showSDPD;
        else if (source === "SDFD") showSDFD = !showSDFD;
        else if (source === "INACTIVE") showInactive = !showInactive;
        updateMarkers();
    }

    async function fetchAllIncidents() {
        try {
            const res = await fetch("/api/incidents?limit=150");
            if (!res.ok) return;
            const data = await res.json();
            allIncidents = data
                .filter((inc) => inc && inc.incident_no && inc.timestamp)
                .map((inc) => ({
                    id: inc.incident_no,
                    timestamp: inc.timestamp,
                    time: formatTimestamp(inc.timestamp),
                    description: inc.description || "No description available",
                    location: inc.location || "Unknown location",
                    neighborhood: inc.neighborhood || "",
                    latitude: inc.latitude ?? null,
                    longitude: inc.longitude ?? null,
                    type: inc.type || "Incident",
                    active: Boolean(inc.active),
                    source: inc.source || "",
                    details: Array.isArray(inc.Details) ? inc.Details : [],
                }));
            updateMarkers();
        } catch (err) {
            console.error("MapTab: Error fetching incidents:", err);
        }
    }

    const PMTILES_URL = "/map_tiles/sandiego.pmtiles";

    onMount(() => {
        // Add PMTiles protocol
        let protocol = new pmtiles.Protocol();
        maplibregl.addProtocol("pmtiles", protocol.tile);

        // DEFCON-style dark command center map
        /** @type {import('maplibre-gl').StyleSpecification} */
        const style = {
            version: 8,
            name: "DEFCON Dark",
            sources: {
                sandiego: {
                    type: "vector",
                    url: "pmtiles://" + PMTILES_URL,
                },
            },
            // Local self-hosted glyphs (Noto Sans PBF fonts)
            glyphs: "/fonts/{fontstack}/{range}.pbf",
            layers: [
                // ── Background ──
                {
                    id: "background",
                    type: "background",
                    paint: {
                        "background-color": "#08090a",
                    },
                },
                // ── Earth / Land ──
                {
                    id: "earth",
                    source: "sandiego",
                    "source-layer": "earth",
                    type: "fill",
                    paint: {
                        "fill-color": "#0f1114",
                    },
                },
                // ── Landcover (forests, grass at low zoom) ──
                {
                    id: "landcover",
                    source: "sandiego",
                    "source-layer": "landcover",
                    type: "fill",
                    paint: {
                        "fill-color": "#0d120e",
                        "fill-opacity": 0.5,
                    },
                },
                // ── Landuse (parks, industrial, etc.) ──
                {
                    id: "landuse_park",
                    source: "sandiego",
                    "source-layer": "landuse",
                    filter: [
                        "in",
                        "kind",
                        "park",
                        "nature_reserve",
                        "garden",
                        "golf_course",
                        "recreation_ground",
                        "cemetery",
                        "forest",
                        "wood",
                    ],
                    type: "fill",
                    paint: {
                        "fill-color": "#0a1a0e",
                        "fill-opacity": 0.6,
                    },
                },
                {
                    id: "landuse_industrial",
                    source: "sandiego",
                    "source-layer": "landuse",
                    filter: [
                        "in",
                        "kind",
                        "industrial",
                        "railway",
                        "commercial",
                    ],
                    type: "fill",
                    paint: {
                        "fill-color": "#12100e",
                        "fill-opacity": 0.4,
                    },
                },
                {
                    id: "landuse_school",
                    source: "sandiego",
                    "source-layer": "landuse",
                    filter: [
                        "in",
                        "kind",
                        "school",
                        "university",
                        "college",
                        "hospital",
                    ],
                    type: "fill",
                    paint: {
                        "fill-color": "#110e14",
                        "fill-opacity": 0.4,
                    },
                },
                // ── Water ──
                {
                    id: "water",
                    source: "sandiego",
                    "source-layer": "water",
                    type: "fill",
                    paint: {
                        "fill-color": "#060d14",
                    },
                },
                // ── Boundaries ──
                {
                    id: "boundaries",
                    source: "sandiego",
                    "source-layer": "boundaries",
                    type: "line",
                    paint: {
                        "line-color": "#1a3a2a",
                        "line-width": 1,
                        "line-dasharray": [4, 3],
                        "line-opacity": 0.6,
                    },
                },
                // ── Buildings ──
                {
                    id: "buildings",
                    source: "sandiego",
                    "source-layer": "buildings",
                    type: "fill",
                    minzoom: 13,
                    paint: {
                        "fill-color": "#111418",
                        "fill-outline-color": "#1c2028",
                    },
                },
                // ── Roads (bottom to top: minor → major → highway) ──
                {
                    id: "road_other",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "other"],
                    type: "line",
                    minzoom: 14,
                    paint: {
                        "line-color": "#1a1d22",
                        "line-width": 0.5,
                    },
                },
                {
                    id: "road_minor",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "minor_road"],
                    type: "line",
                    minzoom: 12,
                    paint: {
                        "line-color": "#222730",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            12,
                            0.5,
                            16,
                            2,
                        ],
                    },
                },
                {
                    id: "road_medium",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "medium_road"],
                    type: "line",
                    paint: {
                        "line-color": "#2a3040",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            8,
                            0.5,
                            14,
                            3,
                        ],
                    },
                },
                {
                    id: "road_major",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "major_road"],
                    type: "line",
                    paint: {
                        "line-color": "#353e52",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            6,
                            0.5,
                            12,
                            2,
                            16,
                            4,
                        ],
                    },
                },
                // Highway casing (outline glow)
                {
                    id: "road_highway_casing",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#1a3366",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            6,
                            2,
                            12,
                            5,
                            16,
                            8,
                        ],
                        "line-opacity": 0.4,
                    },
                },
                // Highway fill
                {
                    id: "road_highway",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#2a55cc",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            6,
                            1,
                            12,
                            2.5,
                            16,
                            5,
                        ],
                        "line-opacity": 0.85,
                    },
                },
                // ── Road Labels ──
                {
                    id: "road_label_highway",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["all", ["==", "kind", "highway"], ["has", "ref"]],
                    type: "symbol",
                    minzoom: 7,
                    layout: {
                        "text-field": "{ref}",
                        "text-font": ["Noto Sans Medium"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            7,
                            8,
                            10,
                            10,
                            14,
                            12,
                        ],
                        "symbol-placement": "line",
                        "symbol-spacing": 400,
                        "text-rotation-alignment": "map",
                        "text-max-angle": 30,
                    },
                    paint: {
                        "text-color": "#7799ee",
                        "text-halo-color": "#0a0e16",
                        "text-halo-width": 2,
                    },
                },
                {
                    id: "road_label_major",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: [
                        "all",
                        ["in", "kind", "major_road", "medium_road"],
                        ["has", "name"],
                    ],
                    type: "symbol",
                    minzoom: 11,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            11,
                            8,
                            14,
                            11,
                            16,
                            13,
                        ],
                        "symbol-placement": "line",
                        "symbol-spacing": 300,
                        "text-rotation-alignment": "map",
                        "text-max-angle": 25,
                    },
                    paint: {
                        "text-color": "#667788",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1.5,
                    },
                },
                {
                    id: "road_label_minor",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: [
                        "all",
                        ["==", "kind", "minor_road"],
                        ["has", "name"],
                    ],
                    type: "symbol",
                    minzoom: 14,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 10,
                        "symbol-placement": "line",
                        "symbol-spacing": 250,
                        "text-rotation-alignment": "map",
                        "text-max-angle": 25,
                    },
                    paint: {
                        "text-color": "#556677",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1,
                    },
                },
                // ── Water Labels ──
                {
                    id: "water_label",
                    source: "sandiego",
                    "source-layer": "water",
                    filter: ["has", "name"],
                    type: "symbol",
                    minzoom: 11,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 11,
                        "text-letter-spacing": 0.15,
                    },
                    paint: {
                        "text-color": "#2a4466",
                        "text-halo-color": "#060d14",
                        "text-halo-width": 1,
                    },
                },
                // ── POI Labels ──
                {
                    id: "poi_label",
                    source: "sandiego",
                    "source-layer": "pois",
                    filter: ["has", "name"],
                    type: "symbol",
                    minzoom: 14,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 10,
                        "text-offset": [0, 0.8],
                        "text-anchor": "top",
                    },
                    paint: {
                        "text-color": "#556b5f",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1,
                    },
                },
                // ── Place Labels (cities, towns, neighborhoods) ──
                {
                    id: "place_label_neighbourhood",
                    source: "sandiego",
                    "source-layer": "places",
                    type: "symbol",
                    filter: [
                        "in",
                        "kind",
                        "neighbourhood",
                        "suburb",
                        "locality",
                    ],
                    minzoom: 10,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            10,
                            9,
                            13,
                            12,
                            15,
                            14,
                        ],
                        "text-transform": "uppercase",
                        "text-letter-spacing": 0.1,
                        "text-allow-overlap": true,
                    },
                    paint: {
                        "text-color": "#cccccc",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 1.5,
                    },
                },
                {
                    id: "place_label_town",
                    source: "sandiego",
                    "source-layer": "places",
                    type: "symbol",
                    filter: ["in", "kind", "town", "village", "hamlet"],
                    minzoom: 7,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Medium"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            7,
                            10,
                            10,
                            13,
                            14,
                            17,
                        ],
                        "text-transform": "uppercase",
                        "text-letter-spacing": 0.08,
                        "text-allow-overlap": true,
                    },
                    paint: {
                        "text-color": "#e0e0e0",
                        "text-halo-color": "#080a0e",
                        "text-halo-width": 2,
                    },
                },
                {
                    id: "place_label_city",
                    source: "sandiego",
                    "source-layer": "places",
                    type: "symbol",
                    filter: ["in", "kind", "city", "state", "country"],
                    minzoom: 4,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Medium"],
                        "text-size": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            4,
                            12,
                            8,
                            16,
                            12,
                            22,
                        ],
                        "text-transform": "uppercase",
                        "text-letter-spacing": 0.15,
                        "text-allow-overlap": true,
                    },
                    paint: {
                        "text-color": "#ffffff",
                        "text-halo-color": "#050a08",
                        "text-halo-width": 3,
                    },
                },
            ],
        };

        map = new maplibregl.Map({
            container: mapContainer,
            style: style,
            center: [-117.1611, 32.7157], // San Diego coordinates
            zoom: 10,
            minZoom: 9,
            maxZoom: 18,
            maxBounds: [
                [-117.9, 32.2], // Southwest corner
                [-116.5, 33.35], // Northeast corner
            ],
            hash: false,
        });

        map.addControl(new maplibregl.NavigationControl(), "top-right");

        // Add geolocate control to the map
        map.addControl(
            new maplibregl.GeolocateControl({
                positionOptions: {
                    enableHighAccuracy: true,
                },
                trackUserLocation: true,
            }),
            "top-right",
        );

        // Fetch incidents immediately! Don't wait for large PMTiles maps or styles to finish loading or parsing
        fetchAllIncidents();
        refreshInterval = setInterval(fetchAllIncidents, 60000);

        map.on("load", () => {
            console.log("MapLibre GL map loaded with PMTiles — DEFCON theme");
        });

        return () => {
            if (refreshInterval) clearInterval(refreshInterval);
            if (map) {
                // Remove all markers before destroying map
                Object.values(markers).forEach((m) => m.marker.remove());
                map.remove();
            }
            maplibregl.removeProtocol("pmtiles");
        };
    });

    function updateMarkers() {
        if (!map || !allIncidents) return;

        const now = Date.now();
        const fourHoursMs = 4 * 60 * 60 * 1000;

        // Show all active incidents + inactive within last 4 hours, filtered by source
        const activeIncidents = allIncidents.filter((inc) => {
            if (!inc.latitude || !inc.longitude) return false;
            // Source filter
            if (inc.source === "CHP" && !showCHP) return false;
            if (inc.source === "SDPD" && !showSDPD) return false;
            if (inc.source === "SDFD" && !showSDFD) return false;
            if (inc.active) return true;
            // Inactive: only show if within last 4 hours
            const incTime = new Date(inc.timestamp).getTime();
            return now - incTime <= fourHoursMs;
        });

        const activeIds = new Set(activeIncidents.map((i) => i.id));

        // Remove old markers that are no longer active
        for (const [id, markerObj] of Object.entries(markers)) {
            if (!activeIds.has(id)) {
                markerObj.marker.remove();
                unmount(markerObj.component);
                delete markers[id];
            }
        }

        // Add or update markers
        activeIncidents.forEach((inc) => {
            if (!markers[inc.id]) {
                // Create a container element for the Svelte component
                const el = document.createElement("div");

                // Instantiate the component using Svelte 5 mount()
                const component = mount(IncidentMarker, {
                    target: el,
                    props: { incident: inc },
                });

                // Create and add MapLibre marker
                const marker = new maplibregl.Marker({ element: el })
                    .setLngLat([inc.longitude, inc.latitude])
                    .addTo(map);

                markers[inc.id] = { marker, component, element: el };
            } else {
                // For Svelte 5: re-mount with updated props
                const existing = markers[inc.id];
                existing.marker.setLngLat([inc.longitude, inc.latitude]);
                // Unmount old, mount new with updated data
                unmount(existing.component);
                existing.element.innerHTML = "";
                existing.component = mount(IncidentMarker, {
                    target: existing.element,
                    props: { incident: inc },
                });
            }
        });
    }
</script>

<div class="map-wrapper">
    <div class="map-container" bind:this={mapContainer}></div>
    <div class="map-filters">
        <button
            class="filter-btn"
            class:active={showCHP}
            on:click={() => toggleFilter("CHP")}
        >
            <span
                class="filter-dot"
                style="background: {showCHP ? '#ffaa33' : '#555'};"
            ></span>
            TRAFFIC
        </button>
        <button
            class="filter-btn"
            class:active={showSDPD}
            on:click={() => toggleFilter("SDPD")}
        >
            <span
                class="filter-dot"
                style="background: {showSDPD ? '#3366ff' : '#555'};"
            ></span>
            POLICE
        </button>
        <button
            class="filter-btn"
            class:active={showSDFD}
            on:click={() => toggleFilter("SDFD")}
        >
            <span
                class="filter-dot"
                style="background: {showSDFD ? '#ff3333' : '#555'};"
            ></span>
            FIRE
        </button>
        <button
            class="filter-btn"
            class:active={showInactive}
            on:click={() => toggleFilter("INACTIVE")}
        >
            <span
                class="filter-dot"
                style="background: {showInactive ? '#888888' : '#555'};"
            ></span>
            INACTIVE
        </button>
    </div>
</div>

<style>
    .map-wrapper {
        position: relative;
    }

    .map-container {
        width: 100%;
        height: calc(100vh - 160px);
        min-height: 400px;
        border-radius: 4px;
        border: 1px solid var(--border-color);
        overflow: hidden;
        position: relative;
        background-color: #08090a;
    }

    .map-filters {
        position: absolute;
        top: 12px;
        left: 12px;
        display: flex;
        gap: 6px;
        z-index: 1000;
    }

    .filter-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: rgba(8, 12, 18, 0.85);
        border: 1px solid rgba(136, 170, 255, 0.25);
        border-radius: 3px;
        color: #667788;
        font-family: "Share Tech Mono", monospace;
        font-size: 0.7rem;
        letter-spacing: 0.08em;
        cursor: pointer;
        transition: all 0.15s ease;
        backdrop-filter: blur(4px);
    }

    .filter-btn.active {
        color: #ddeeff;
        border-color: rgba(136, 170, 255, 0.5);
        background: rgba(8, 12, 18, 0.95);
    }

    .filter-btn:hover {
        border-color: rgba(136, 170, 255, 0.6);
        background: rgba(15, 25, 40, 0.95);
    }

    .filter-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    :global(.maplibregl-ctrl-group) {
        background: rgba(0, 0, 0, 0.7) !important;
        border: 1px solid #1a3a2a !important;
    }

    :global(.maplibregl-ctrl-group button) {
        background: transparent !important;
        border-bottom: 1px solid #1a3a2a !important;
    }

    :global(.maplibregl-ctrl-group button:last-child) {
        border-bottom: none !important;
    }

    :global(.maplibregl-ctrl-icon) {
        filter: invert(1) sepia(0.3) hue-rotate(90deg);
    }

    :global(.maplibregl-ctrl-attrib) {
        background: rgba(0, 0, 0, 0.5) !important;
        color: #334433 !important;
        font-size: 10px !important;
    }

    :global(.maplibregl-ctrl-attrib a) {
        color: #446644 !important;
    }
</style>
