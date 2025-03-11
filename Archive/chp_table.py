import requests
from bs4 import BeautifulSoup
import schedule
import time
from pprint import pprint
from termcolor import colored
import re
from geopy.geocoders import Nominatim

# URL of the page to scrape
url = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"

# Constants for the second script
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
}
PARAMS = {'ddlComCenter': 'BCCC'}
VIEWSTATE_PATTERN = re.compile(r'<input\s+type="hidden"\s+name="__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]+)"\s*/?>')
LAT_LON_PATTERN = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
BRACKETS_PATTERN = re.compile(r'\[.*?\]')

# Store the previous data
previous_data = None

EXCLUDED_DETAILS = {'Unit At Scene', 'Unit Enroute', 'Unit Assigned'}

def scrape_table():
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Locate the table
    table = soup.find('table', id='gvIncidents')
    
    # Extract table headers
    headers = [th.text.strip() for th in table.find_all('th')]
    
    # Extract the first row of the table
    first_row = table.find_all('tr')[1]  # skip the header row
    cells = first_row.find_all('td')
    row_data = [cell.text.strip() for cell in cells]
    
    # Create a dictionary excluding the "Area" key
    table_data = dict(zip(headers, row_data))
    table_data.pop('Area', None)  # Remove 'Area' if it exists
    
    return table_data

def get_viewstate(response_text):
    match = VIEWSTATE_PATTERN.search(response_text)
    return match.group(1) if match else None

def extract_traffic_info(response_text):
    matches = LAT_LON_PATTERN.findall(response_text)
    pattern = re.compile(r'<td[^>]*colspan="6"[^>]*>(.*?)</td>', re.DOTALL)
    details_matches = pattern.findall(response_text)

    # Process details into a list of strings and exclude unwanted details
    details = [BRACKETS_PATTERN.sub('', match).strip() for match in details_matches if match not in EXCLUDED_DETAILS]
    
    if matches:
        for match in matches:
            lat_str, lon_str = match.split()
            # Validate latitude and longitude precision
            if len(lat_str.split('.')[-1]) == 6 and len(lon_str.split('.')[-1]) == 6:
                return {
                    "Latitude": float(lat_str),
                    "Longitude": float(lon_str),
                    "Details": details
                }
    return None

def get_location(lat, lon):
    """
    Returns the location (city, neighborhood, state, country, etc.) for given latitude and longitude.
    
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
        return location.raw.get('address', {})
    else:
        return {}

def get_coordinates():
    try:
        response = requests.get(url)
        response.raise_for_status()

        viewstate_value = get_viewstate(response.text)
        if not viewstate_value:
            print("No __VIEWSTATE found on the page.")
            return None

        data = {
            '__LASTFOCUS': '',
            '__EVENTTARGET': 'gvIncidents',
            '__EVENTARGUMENT': 'Select$0',
            '__VIEWSTATE': viewstate_value,
            '__VIEWSTATEGENERATOR': 'B13DF00D',
            'ddlComCenter': 'BCCC',
            'ddlSearches': 'Choose One',
            'ddlResources': 'Choose One',
        }

        response = requests.post(url, params=PARAMS, headers=HEADERS, data=data)
        response.raise_for_status()

        coordinates_data = extract_traffic_info(response.text)
        
        if coordinates_data:
            # Get location information (including neighborhood)
            location_info = get_location(coordinates_data['Latitude'], coordinates_data['Longitude'])
            coordinates_data['Neighborhood'] = location_info.get('neighbourhood', 'N/A')
            coordinates_data['City'] = location_info.get('city', 'N/A')

        return coordinates_data

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

# Function to check for updates
def check_for_updates():
    global previous_data
    
    # Scrape the table
    table_data = scrape_table()
    
    # Get the coordinates and details
    coordinates_data = get_coordinates()
    
    if coordinates_data:
        # Merge the two dictionaries
        merged_data = {**table_data, **coordinates_data}

        # Check if the data has changed
        if merged_data != previous_data:
            print(colored("First Row Data Updated at " + time.strftime("%Y-%m-%d %H:%M:%S"), "green"))
            pprint(merged_data)
        
            # Update the previous data with the new data
            previous_data = merged_data

# Schedule the check_for_updates function to run every 30 seconds
schedule.every(30).seconds.do(check_for_updates)

# Initial call to display the data immediately
check_for_updates()

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
