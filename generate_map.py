"""
Legacy entrypoint kept for older maintenance scripts.

The frontend now renders incident mini maps directly from longitude/latitude
using the local PMTiles basemap, so the scraper no longer needs to generate
Mapbox static images.
"""

import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR = os.path.join(BASE_DIR, "traffic-app", "maps")
os.makedirs(TARGET_DIR, exist_ok=True)


def save_map_image(lon, lat, filename="map.png"):
    print(
        "Static map generation is disabled. "
        "Incident maps are rendered client-side from PMTiles."
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("No coordinates provided. Exiting.")
        sys.exit(1)

    save_map_image(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) >= 4 else "map.png")
