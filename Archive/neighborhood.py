from geopy.geocoders import Nominatim

def get_location_info(lat, lon):
    geolocator = Nominatim(user_agent="geopy")
    location = geolocator.reverse((lat, lon), exactly_one=True)
    
    if location and location.raw.get('address'):
        address = location.raw['address']
        location_info = {
            "Country": address.get('country', None),
            "State": address.get('state', None),
            "City": address.get('city', None),
            "County": address.get('county', None),
            "Suburb": address.get('suburb', None),
            "Neighbourhood": address.get('neighbourhood', None),
            "Road": address.get('road', None),
            "Postcode": address.get('postcode', None),
            "Latitude": location.latitude,
            "Longitude": location.longitude,
            "Display Name": location.address
        }
        return location_info
    else:
        return None

# Example usage
latitude = 33.519039
longitude = -117.160446

location_info = get_location_info(latitude, longitude)
print("Location Information:")
for key, value in location_info.items():
    print(f"{key}: {value}")
