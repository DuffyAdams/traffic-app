import requests
import datetime
import pytz
from dotenv import load_dotenv
import os

load_dotenv()

MAPBOX_BASE_URL = "https://api.mapbox.com/styles/v1/mapbox/"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Build the target folder: roadAlerts/traffic-app/maps
TARGET_DIR = os.path.join(BASE_DIR, "traffic-app", "maps")
if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)

def generate_mapbox_url(lon, lat, access_token, zoom=16, bearing=0, pitch=60, size='500x500', dark_mode=False):
    """
    Generate a Mapbox URL for a static map image.
    """
    style = "satellite-streets-v12"  # Same style regardless of dark_mode for now
    url = (
        f"{MAPBOX_BASE_URL}{style}/static/"
        f"pin-s+ff4242({lon},{lat})/{lon},{lat},{zoom},{bearing},{pitch}/{size}"
        f"?access_token={access_token}"
    )
    return url

def is_after_sunset(lon, lat):
    """
    Determine if the current local time at the given location is after sunset.
    """
    local_timezone = pytz.timezone('America/Los_Angeles')
    now = datetime.datetime.now(local_timezone)
    sunset = datetime.datetime(now.year, now.month, now.day, 19, 0, 0, tzinfo=local_timezone)
    return now > sunset

def save_map_image(lon, lat, access_token, filename='map.png'):
    """
    Download and save a static map image from Mapbox.
    """
    dark_mode = is_after_sunset(lon, lat)
    url = generate_mapbox_url(lon, lat, access_token, dark_mode=dark_mode)
    response = requests.get(url)
    response.raise_for_status()
    
    # Ensure the filename is a full path, if not, prepend TARGET_DIR
    if not os.path.isabs(filename):
        filename = os.path.join(TARGET_DIR, os.path.basename(filename))
        
    with open(filename, 'wb') as file:
        file.write(response.content)
    print(f"Map image saved as {filename}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        try:
            lon = float(sys.argv[1])
            lat = float(sys.argv[2])
        except ValueError:
            print("Invalid coordinate values provided. Exiting.")
            exit(1)
    else:
        print("No Arguments Provided. Exiting.")
        exit(1)

    # If a filename is provided as the third argument, use it.
    if len(sys.argv) >= 4:
        filename = sys.argv[3]
    else:
        # Generate filename based on current time and save it in the TARGET_DIR.
        local_timezone = pytz.timezone('America/Los_Angeles')
        incident_time = datetime.datetime.now(local_timezone)
        filename_date_str = incident_time.strftime("%Y%m%d_%H%M")
        filename = f"map_{filename_date_str}.png"

    access_token = os.getenv("MAP_ACCESS_TOKEN")
    if not access_token:
        print("MAP_ACCESS_TOKEN not found in environment variables.")
    else:
        save_map_image(lon, lat, access_token, filename)