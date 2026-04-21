from geopy.geocoders import ArcGIS
import json

geolocator = ArcGIS()
loc = geolocator.reverse((33.217243986771, -117.230393410302))

if loc:
    print(json.dumps(loc.raw, indent=2))
else:
    print("No location found.")
