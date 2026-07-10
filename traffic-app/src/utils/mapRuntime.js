const PMTILES_PROTOCOL = "pmtiles";

export const PMTILES_URL = "/map_tiles/sandiego.pmtiles";

let librariesPromise = null;
let protocolRegistered = false;

/**
 * Load MapLibre and PMTiles once and keep one shared PMTiles protocol/cache for
 * every full-size and incident map in the application.
 */
export function loadMapLibraries() {
    if (!librariesPromise) {
        librariesPromise = Promise.all([
            import("maplibre-gl"),
            import("pmtiles"),
        ])
            .then(([maplibreModule, pmtilesModule]) => {
                const maplibregl = maplibreModule.default;

                if (!protocolRegistered) {
                    const protocol = new pmtilesModule.Protocol();
                    maplibregl.addProtocol(PMTILES_PROTOCOL, protocol.tile);
                    protocolRegistered = true;
                }

                return { maplibregl };
            })
            .catch((error) => {
                // A transient chunk/network failure should be retryable the next
                // time a map enters the viewport.
                librariesPromise = null;
                throw error;
            });
    }

    return librariesPromise;
}
