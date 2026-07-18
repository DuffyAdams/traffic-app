"""Manually inspect one ArcGIS reverse-geocoding response."""

import json

from geopy.geocoders import ArcGIS


def main():
    location = ArcGIS().reverse((33.217243986771, -117.230393410302))
    print(json.dumps(location.raw, indent=2) if location else "No location found.")


if __name__ == "__main__":
    main()
