"""Manually check ArcGIS forward geocoding against sample San Diego addresses."""

from geopy.geocoders import ArcGIS


ADDRESSES = (
    "11900 WOODSIDE AV",
    "E BOBIER DR and CALLE JULES",
    "2400 SKYLINE DR",
)


def main():
    geolocator = ArcGIS()
    print("Geocoding sample San Diego County addresses with ArcGIS:\n")
    for address in ADDRESSES:
        query = f"{address}, San Diego County, CA"
        print(f"Query: {query}")
        try:
            location = geolocator.geocode(query)
        except Exception as exc:
            print(f"Error: {exc}\n")
            continue

        if location:
            print(f"Result: {location.latitude}, {location.longitude}")
            print(f"Matched: {location.address}\n")
        else:
            print("Result: Not found\n")


if __name__ == "__main__":
    main()
