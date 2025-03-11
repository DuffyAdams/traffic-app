from geopy.geocoders import Nominatim

def get_location(lat, lon):
    """
    Returns the location (city, state, country, etc.) for given latitude and longitude.
    
    Args:
        lat (float): Latitude value.
        lon (float): Longitude value.
    
    Returns:
        dict: A dictionary containing the location details.
    """
    # Initialize the geolocator
    geolocator = Nominatim(user_agent="GEOPY")
    
    # Perform reverse geocoding
    location = geolocator.reverse((lat, lon), exactly_one=True)
    
    if location:
        return location.raw['address']
    else:
        return None

# Example usage:
latitude = 37.7749
longitude = -122.4194
location = get_location(latitude, longitude)

if location:
    print(f"Location details: {location}")
else:
    print("Location not found.")
