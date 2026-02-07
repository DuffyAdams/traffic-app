import googlemaps
import time

GOOGLE_API_KEY = "AIzaSyDEDdhk8a93T0dBh1lYyRdFz6NU_2fUe4k"

gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

def geocode_with_debug(address: str):
    try:
        results = gmaps.geocode(address)
    except Exception as e:
        print(f"DEBUG: google exception for '{address}': {e}")
        return None

    if not results:
        print(f"DEBUG: no google results for '{address}'")
        return None

    top = results[0]
    loc = top["geometry"]["location"]
    formatted = top.get("formatted_address", "n/a")
    place_id = top.get("place_id", "n/a")
    location_type = top.get("geometry", {}).get("location_type", "n/a")

    print(f"DEBUG: google hit for '{address}' -> '{formatted}'")
    print(f"DEBUG: location_type={location_type}, place_id={place_id}")
    return (loc["lat"], loc["lng"])

addresses = [
    "Laurel St & 5th Ave, San Diego, CA",
    "5th Ave & Laurel St, San Diego, CA",
    "Laurel St at 5th Ave, San Diego, CA",
    "5th Ave at Laurel St, San Diego, CA",
    "Laurel St & 5TH AVE, San Diego, CA",
    "5TH AVE & Laurel St, San Diego, CA",
    "Laurel St & Fifth Ave, San Diego, CA",
    "Fifth Ave & Laurel St, San Diego, CA",
    "Laurel St & Fifth Ave, Balboa Park, San Diego, CA",
    "Laurel St & El Prado, Balboa Park, San Diego, CA",
    "El Prado, Balboa Park, San Diego, CA",
]

found = None
for addr in addresses:
    found = geocode_with_debug(addr)
    if found:
        print(f"\nFINAL: matched address '{addr}' -> lat/lng = {found}\n")
        break
    time.sleep(0.1)  # small pause to be polite

if not found:
    print("\nFINAL: location not found for any variant\n")
