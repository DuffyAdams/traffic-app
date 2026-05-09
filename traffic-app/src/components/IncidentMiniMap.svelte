<script context="module">
    import "maplibre-gl/dist/maplibre-gl.css";

    const MAX_ACTIVE_MINI_MAPS = 8;
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
            const evictionIndex = activeMiniMaps.findIndex(
                (item) =>
                    item !== instance &&
                    (!item.isNearViewport() || !item.isMapReady()),
            );

            if (evictionIndex === -1) {
                // Keep already-visible ready maps alive even if we temporarily
                // exceed the soft cap, otherwise live cards blur when new
                // incidents mount above them.
                break;
            }

            const [evicted] = activeMiniMaps.splice(evictionIndex, 1);
            evicted?.deactivate();
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
    const MINI_MAP_ZOOM = 12.1;
    let shell;
    let mapContainer;
    let map;
    let observer;
    let resizeObserver;
    let isNearViewport = false;
    let canRenderMap = false;
    let mapReady = false;
    let hasRenderedOnce = false;
    let mapUnavailable = false;
    let isDestroyed = false;
    let initRequestId = 0;
    let lastCoordinateKey = "";

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
        isNearViewport() {
            return isNearViewport;
        },
        isMapReady() {
            return mapReady;
        },
    };

    function requestMapSlot() {
        if (!isNearViewport) return;
        mapUnavailable = false;
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
            mapUnavailable ||
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
            mapUnavailable ||
            longitude == null ||
            latitude == null ||
            !mapContainer ||
            !document.body.contains(mapContainer)
        ) {
            return;
        }

        ensureProtocol();
        mapReady = false;

        try {
            map = new maplibregl.Map({
                container: mapContainer,
                style: getStyle(),
                center: [longitude, latitude],
                zoom: MINI_MAP_ZOOM,
                interactive: false,
                attributionControl: false,
                fadeDuration: 0,
            });
        } catch (error) {
            console.warn("IncidentMiniMap: failed to create map", error);
            handleMapUnavailable();
            return;
        }

        startResizeObserver();

        map.once("error", (event) => {
            console.warn("IncidentMiniMap: map failed to load", event?.error || event);
            handleMapUnavailable();
        });

        map.once("load", () => {
            updatePosition();
            requestAnimationFrame(() => {
                if (map) {
                    map.resize();
                }
            });
        });

        map.once("idle", () => {
            validateRenderedMap();
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
        mapReady = false;
    }

    function handleMapUnavailable() {
        mapUnavailable = true;
        canRenderMap = false;
        initRequestId++;
        destroyMap();
    }

    function validateRenderedMap() {
        if (!map || isDestroyed) return;

        const renderedFeatures = map.queryRenderedFeatures({
            layers: [
                "earth",
                "landuse_park",
                "water",
                "buildings",
                "road_minor",
                "road_major",
                "road_highway_casing",
                "road_highway",
                "road_label_major",
            ],
        });

        if (renderedFeatures.length === 0) {
            handleMapUnavailable();
            return;
        }

        mapReady = true;
        hasRenderedOnce = true;
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

    function resetForCoordinateChange() {
        const coordinateKey = `${latitude ?? ""},${longitude ?? ""}`;
        if (coordinateKey === lastCoordinateKey) return;

        lastCoordinateKey = coordinateKey;
        mapUnavailable = false;
        mapReady = false;
        initRequestId++;
        destroyMap(false);
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

    $: resetForCoordinateChange();
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
    class:loading={!mapReady && !hasRenderedOnce}
    bind:this={shell}
    style="--marker-color: {markerColor};"
>
    <div
        class:ready={mapReady}
        class:loaded-before={hasRenderedOnce}
        class="mini-map-fallback"
        aria-hidden="true"
    >
        <span class="fallback-road fallback-road-one"></span>
        <span class="fallback-road fallback-road-two"></span>
        <span class="fallback-road fallback-road-three"></span>
    </div>
    {#if isNearViewport && canRenderMap}
        <div
            class:ready={mapReady}
            class:loaded-before={hasRenderedOnce}
            class="mini-map"
            bind:this={mapContainer}
        ></div>
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

    .mini-map-fallback,
    .mini-map {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
    }

    .mini-map-fallback {
        background:
            linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px),
            linear-gradient(0deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px),
            radial-gradient(
                circle at center,
                color-mix(in srgb, var(--marker-color, #fbbf24) 16%, transparent),
                transparent 34%
            ),
            linear-gradient(135deg, #0a1018, #07090d 62%, #10131a);
        background-size:
            36px 36px,
            36px 36px,
            auto,
            auto;
        opacity: 0.95;
        filter: blur(14px);
        transform: scale(1.05);
        transition:
            filter 220ms ease,
            opacity 220ms ease,
            transform 220ms ease;
    }

    .mini-map-fallback.ready {
        opacity: 0.28;
        filter: blur(0);
        transform: scale(1);
    }

    .mini-map-fallback.loaded-before:not(.ready) {
        opacity: 0.28;
        filter: blur(0);
        transform: scale(1);
    }

    .fallback-road {
        position: absolute;
        height: 3px;
        border-radius: 999px;
        background: rgba(74, 90, 120, 0.8);
        box-shadow: 0 0 10px rgba(37, 99, 235, 0.16);
        transform-origin: center;
    }

    .fallback-road-one {
        left: -12%;
        top: 30%;
        width: 78%;
        transform: rotate(-8deg);
    }

    .fallback-road-two {
        right: -10%;
        top: 58%;
        width: 72%;
        transform: rotate(11deg);
    }

    .fallback-road-three {
        left: 44%;
        top: -8%;
        width: 3px;
        height: 118%;
        background: rgba(47, 102, 255, 0.75);
        transform: rotate(-16deg);
        box-shadow:
            0 0 0 2px rgba(17, 47, 120, 0.35),
            0 0 14px rgba(47, 102, 255, 0.45);
    }

    .mini-map {
        background: #08090a;
        opacity: 0;
        filter: blur(16px);
        transform: scale(1.04);
        transition: opacity 160ms ease;
        z-index: 1;
    }

    .mini-map.ready {
        opacity: 1;
        filter: blur(0);
        transform: scale(1);
        transition:
            opacity 160ms ease,
            filter 220ms ease,
            transform 220ms ease;
    }

    .mini-map.loaded-before:not(.ready) {
        opacity: 1;
        filter: blur(0);
        transform: scale(1);
    }

    .mini-map-shell.loading::after {
        content: "";
        position: absolute;
        inset: 0;
        z-index: 1;
        pointer-events: none;
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.03) 0%,
            rgba(255, 255, 255, 0.08) 50%,
            rgba(255, 255, 255, 0.03) 100%
        );
        background-size: 200% 100%;
        animation: miniMapShimmer 1.6s linear infinite;
    }

    .mini-incident-icon {
        position: absolute;
        left: 50%;
        top: 50%;
        width: 22px;
        height: 22px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        background: var(--marker-color);
        border: 2px solid #ffffff;
        box-shadow:
            0 0 0 4px color-mix(in srgb, var(--marker-color) 20%, transparent),
            0 0 16px color-mix(in srgb, var(--marker-color) 60%, transparent);
        z-index: 2;
    }

    .mini-incident-icon :global(svg) {
        width: 13px;
        height: 13px;
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

    @keyframes miniMapShimmer {
        0% {
            background-position: -200% 0;
        }
        100% {
            background-position: 200% 0;
        }
    }
</style>
