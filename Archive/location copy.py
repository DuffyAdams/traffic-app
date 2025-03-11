import requests
import re

# Constants
URL = "https://cad.chp.ca.gov/traffic.aspx?ddlComCenter=BCCC"
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
}
PARAMS = {'ddlComCenter': 'BCCC'}
VIEWSTATE_PATTERN = re.compile(r'<input\s+type="hidden"\s+name="__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]+)"\s*/?>')
LAT_LON_PATTERN = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
BRACKETS_PATTERN = re.compile(r'\[.*?\]')

def get_viewstate(response_text):
    match = VIEWSTATE_PATTERN.search(response_text)
    return match.group(1) if match else None

def extract_traffic_info(response_text):
    matches = LAT_LON_PATTERN.findall(response_text)
    pattern = re.compile(r'<td[^>]*colspan="6"[^>]*>(.*?)</td>', re.DOTALL)
    matches_two = pattern.findall(response_text)

    # Combine traffic details into one string and clean up
    traffic = " ".join(match.strip() for match in matches_two)
    traffic = BRACKETS_PATTERN.sub('', traffic).strip()

    if matches:
        for match in matches:
            lat_str, lon_str = match.split()
            # Validate latitude and longitude precision
            if len(lat_str.split('.')[-1]) == 6 and len(lon_str.split('.')[-1]) == 6:
                return {
                    "Latitude": float(lat_str),
                    "Longitude": float(lon_str),
                    "Details": traffic
                }
    return None

def get_coordinates():
    try:
        response = requests.get(URL)
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

        response = requests.post(URL, params=PARAMS, headers=HEADERS, data=data)
        response.raise_for_status()

        result = extract_traffic_info(response.text)
        if result:
            return result
        else:
            print("No valid latitude and longitude found.")
            return None

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

if __name__ == "__main__":
    result = get_coordinates()
    if result:
        print(result)
