<script context="module">
    import "maplibre-gl/dist/maplibre-gl.css";

    const MAX_ACTIVE_MINI_MAPS = 4;
    let activeMiniMaps = [];
    let protocolRegistered = false;
    let mapLibPromise = null;
    let maplibregl = null;
    let pmtiles = null;

    async function loadMapLibraries() {
        if (!mapLibPromise) {
            mapLibPromise = Promise.all([import("maplibre-gl"), import("pmtiles")]).then(
                ([maplibreModule, pmtilesModule]) => {
                    maplibregl = maplibreModule.default;
                    pmtiles = pmtilesModule;
                    return { maplibregl, pmtiles };
                },
            );
        }

        return mapLibPromise;
    }

    function ensureProtocol() {
        if (protocolRegistered) return;
        const protocol = new pmtiles.Protocol();
        maplibregl.addProtocol("pmtiles", protocol.tile);
        protocolRegistered = true;
    }

    function claimMiniMapSlot(instance) {
        activeMiniMaps = activeMiniMaps.filter((item) => item !== instance);
        activeMiniMaps.push(instance);

        while (activeMiniMaps.length > MAX_ACTIVE_MINI_MAPS) {
            const oldest = activeMiniMaps.shift();
            if (oldest && oldest !== instance) {
                oldest.deactivate();
            }
        }
    }

    function releaseMiniMapSlot(instance) {
        activeMiniMaps = activeMiniMaps.filter((item) => item !== instance);
    }
</script>

<script>
    import { onMount, onDestroy, tick } from "svelte";
    import IncidentIcon from "./IncidentIcon.svelte";

    export let latitude = null;
    export let longitude = null;
    export let type = "Incident";
    export let active = false;

    const PMTILES_URL = "/map_tiles/sandiego.pmtiles";
    const MINI_MAP_ZOOM = 12.8;
    let shell;
    let mapContainer;
    let map;
    let observer;
    let resizeObserver;
    let isNearViewport = false;
    let canRenderMap = false;
    let isDestroyed = false;
    let initRequestId = 0;

    const incidentColors = {
        "Traffic Hazard": "#fbbf24",
        "Traffic Collision": "#ef4444",
        "Car Fire": "#f97316",
        "Report of Fire": "#f97316",
        Fatality: "#991b1b",
        "Hit and Run No Injuries": "#dc2626",
        "Road Closure": "#374151",
        Construction: "#f59e0b",
        "Debris From Vehicle": "#9ca3af",
        "Debris from Vehicle": "#9ca3af",
        "Live or Dead Animal": "#a78bfa",
        "Animal Hazard": "#a78bfa",
        "Defective Traffic Signals": "#eab308",
        JUMPER: "#8b5cf6",
        SPINOUT: "#06b6d4",
        "Wrong Way Driver": "#ec4899",
        "SIG Alert": "#dc2626",
        "Aircraft Emergency": "#3b82f6",
        "Provide Traffic Control": "#6366f1",
        Maintenance: "#6b7280",
        "Road Conditions": "#84cc16",
        "Traffic Break": "#0ea5e9",
        "NO DETAIL ACCIDENT": "#ef4444",
        "MINOR INJURY ACCIDENT": "#ef4444",
        "SERIOUS INJURY ACCIDENT": "#dc2626",
        "MISD HIT/RUN": "#ef4444",
        "HIT AND RUN REPORT": "#ef4444",
        "HAZARDOUS CONDITION": "#fbbf24",
        "BURGLARY ALARM": "#3b82f6",
        BATTERY: "#8b5cf6",
        "PRISONER IN CUSTODY": "#374151",
        "DISTURBING PEACE": "#6366f1",
        "DISTURBING PEACE W/VIOLENCE": "#6366f1",
        "REPORT OF DEATH": "#000000",
        "MENTAL CASE": "#ec4899",
        Medical: "#ef4444",
        MEDICAL: "#ef4444",
        "Traffic Accident (L1)": "#f59e0b",
        "Traffic Accident FWY": "#f59e0b",
        "Vehicle Fire": "#f97316",
    };

    $: markerColor = incidentColors[type] || "#fbbf24";

    const miniMapInstance = {
        deactivate() {
            canRenderMap = false;
            destroyMap(false);
        },
    };

    function requestMapSlot() {
        if (!isNearViewport) return;
        claimMiniMapSlot(miniMapInstance);
        canRenderMap = true;
    }

    function startResizeObserver() {
        if (resizeObserver || !("ResizeObserver" in window) || !shell) return;

        resizeObserver = new ResizeObserver(() => {
            if (map) {
                map.resize();
            }
        });

        resizeObserver.observe(shell);
        if (mapContainer) {
            resizeObserver.observe(mapContainer);
        }
    }

    function stopResizeObserver() {
        if (!resizeObserver) return;
        resizeObserver.disconnect();
        resizeObserver = null;
    }

    async function createMap() {
        const requestId = ++initRequestId;
        if (
            map ||
            !canRenderMap ||
            longitude == null ||
            latitude == null ||
            !mapContainer
        )
            return;

        await loadMapLibraries();
        await tick();

        if (
            isDestroyed ||
            requestId !== initRequestId ||
            map ||
            !canRenderMap ||
            longitude == null ||
            latitude == null ||
            !mapContainer ||
            !document.body.contains(mapContainer)
        ) {
            return;
        }

        ensureProtocol();
        map = new maplibregl.Map({
            container: mapContainer,
            style: getStyle(),
            center: [longitude, latitude],
            zoom: MINI_MAP_ZOOM,
            interactive: false,
            attributionControl: false,
            fadeDuration: 0,
        });

        startResizeObserver();

        map.once("load", () => {
            updatePosition();
            requestAnimationFrame(() => {
                if (map) {
                    map.resize();
                }
            });
        });
    }

    function destroyMap(releaseSlot = true) {
        if (releaseSlot) {
            releaseMiniMapSlot(miniMapInstance);
        }
        stopResizeObserver();
        if (!map) return;
        map.remove();
        map = null;
    }

    function getStyle() {
        return {
            version: 8,
            name: "Incident Mini Map",
            sources: {
                sandiego: {
                    type: "vector",
                    url: "pmtiles://" + PMTILES_URL,
                },
            },
            glyphs: "/fonts/{fontstack}/{range}.pbf",
            layers: [
                {
                    id: "background",
                    type: "background",
                    paint: { "background-color": "#08090a" },
                },
                {
                    id: "earth",
                    source: "sandiego",
                    "source-layer": "earth",
                    type: "fill",
                    paint: { "fill-color": "#101317" },
                },
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
                    ],
                    type: "fill",
                    paint: { "fill-color": "#0a1a0e", "fill-opacity": 0.65 },
                },
                {
                    id: "water",
                    source: "sandiego",
                    "source-layer": "water",
                    type: "fill",
                    paint: { "fill-color": "#06111d" },
                },
                {
                    id: "buildings",
                    source: "sandiego",
                    "source-layer": "buildings",
                    type: "fill",
                    minzoom: 13,
                    paint: {
                        "fill-color": "#171b21",
                        "fill-outline-color": "#252b35",
                    },
                },
                {
                    id: "road_minor",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["in", "kind", "minor_road", "other"],
                    type: "line",
                    minzoom: 12,
                    paint: {
                        "line-color": "#262c36",
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
                    id: "road_major",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["in", "kind", "major_road", "medium_road"],
                    type: "line",
                    paint: {
                        "line-color": "#3d465c",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            10,
                            1,
                            16,
                            4,
                        ],
                    },
                },
                {
                    id: "road_highway_casing",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#112f78",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            8,
                            2,
                            16,
                            8,
                        ],
                        "line-opacity": 0.45,
                    },
                },
                {
                    id: "road_highway",
                    source: "sandiego",
                    "source-layer": "roads",
                    filter: ["==", "kind", "highway"],
                    type: "line",
                    paint: {
                        "line-color": "#2f66ff",
                        "line-width": [
                            "interpolate",
                            ["linear"],
                            ["zoom"],
                            8,
                            1,
                            16,
                            5,
                        ],
                        "line-opacity": 0.9,
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
                    minzoom: 12,
                    layout: {
                        "text-field": "{name}",
                        "text-font": ["Noto Sans Regular"],
                        "text-size": 11,
                        "symbol-placement": "line",
                        "symbol-spacing": 280,
                    },
                    paint: {
                        "text-color": "#8491a6",
                        "text-halo-color": "#08090a",
                        "text-halo-width": 1.5,
                    },
                },
            ],
        };
    }

    function updatePosition() {
        if (!map || longitude == null || latitude == null) return;
        const center = [longitude, latitude];
        map.jumpTo({ center });
    }

    onMount(() => {
        isDestroyed = false;
        if (longitude == null || latitude == null) return;

        if (!("IntersectionObserver" in window)) {
            isNearViewport = true;
            requestMapSlot();
            return;
        }

        observer = new IntersectionObserver(
            ([entry]) => {
                isNearViewport = entry.isIntersecting;
                if (isNearViewport) {
                    requestMapSlot();
                } else {
                    canRenderMap = false;
                    initRequestId++;
                    destroyMap();
                }
            },
            {
                rootMargin: "120px 0px",
                threshold: 0,
            },
        );
        observer.observe(shell);
    });

    $: if (isNearViewport && canRenderMap && mapContainer) void createMap();
    $: updatePosition();

    onDestroy(() => {
        isDestroyed = true;
        initRequestId++;
        if (observer) observer.disconnect();
        destroyMap();
    });
</script>

<div
    class="mini-map-shell"
    bind:this={shell}
    style="--marker-color: {markerColor};"
>
    {#if isNearViewport && canRenderMap}
        <div class="mini-map" bind:this={mapContainer}></div>
    {/if}
    <div
        class:active
        class="mini-incident-icon"
        title={type}
    >
        <IncidentIcon {type} />
    </div>
</div>

<style>
    .mini-map-shell {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background:
            radial-gradient(
                circle at center,
                color-mix(in srgb, var(--marker-color, #fbbf24) 8%, transparent),
                transparent 34%
            ),
            #08090a;
    }

    .mini-map {
        width: 100%;
        height: 100%;
        background: #08090a;
    }

    .mini-incident-icon {
        position: absolute;
        left: 50%;
        top: 50%;
        width: 26px;
        height: 26px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        background: var(--marker-color);
        border: 2px solid #ffffff;
        box-shadow:
            0 0 0 5px color-mix(in srgb, var(--marker-color) 20%, transparent),
            0 0 18px color-mix(in srgb, var(--marker-color) 60%, transparent);
        z-index: 2;
    }

    .mini-incident-icon :global(svg) {
        width: 15px;
        height: 15px;
        stroke-width: 2.5;
    }

    .mini-incident-icon.active {
        animation: miniPulse 1.5s infinite;
    }

    @keyframes miniPulse {
        0% {
            box-shadow:
                0 0 0 4px color-mix(in srgb, var(--marker-color) 22%, transparent),
                0 0 15px color-mix(in srgb, var(--marker-color) 65%, transparent);
        }
        70% {
            box-shadow:
                0 0 0 10px color-mix(in srgb, var(--marker-color) 0%, transparent),
                0 0 22px color-mix(in srgb, var(--marker-color) 75%, transparent);
        }
        100% {
            box-shadow:
                0 0 0 4px color-mix(in srgb, var(--marker-color) 0%, transparent),
                0 0 15px color-mix(in srgb, var(--marker-color) 65%, transparent);
        }
    }
</style>
