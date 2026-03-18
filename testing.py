from geopy.geocoders import ArcGIS

geolocator = ArcGIS()

addresses = [
    "11900 WOODSIDE AV",
    "E BOBIER DR and CALLE JULES",
    "2400 SKYLINE DR"
]

print("Geocoding testing in San Diego County (Using ArcGIS):\n")
for address in addresses:
    full_query = f"{address}, San Diego County, CA"
    print(f"Testing Query: {full_query}")
    try:
        location = geolocator.geocode(full_query)
        if location:
            print(f"Result: {location.latitude}, {location.longitude}")
            print(f"Address Matched: {location.address}\n")
        else:
            print("Result: Not Found\n")
    except Exception as e:
        print(f"Error: {e}\n")