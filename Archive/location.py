import requests
import re

# Constants
URL = "https://cad.chp.ca.gov/traffic.aspx?ddlComCenter=BCCC"
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://cad.chp.ca.gov',
    'Pragma': 'no-cache',
    'Referer': URL,
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}
PARAMS = {'ddlComCenter': 'BCCC'}
VIEWSTATE_PATTERN = re.compile(r'<input\s+type="hidden"\s+name="__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]+)"\s*/?>')
LAT_LON_PATTERN = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
BRACKETS_PATTERN = re.compile(r'\[.*?\]')

def get_viewstate(response_text):
    match = VIEWSTATE_PATTERN.search(response_text)
    if match:
        return match.group(1)
    else:
        print("No __VIEWSTATE found on the page.")
        return None

def get_coordinates():
    try:
        response = requests.get(URL)
        response.raise_for_status()
        viewstate_value = get_viewstate(response.text)
        
        if not viewstate_value:
            return None, None

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

        matches = LAT_LON_PATTERN.findall(response.text)
        #print(response.text)
        pattern = re.compile(r'<td[^>]*colspan="6"[^>]*>(.*?)</td>', re.DOTALL)
        matches_two = pattern.findall(response.text)

        # Extracted data and combine into one string
        traffic = " ".join(match.strip() for match in matches_two)

        # Remove patterns like [anything]
        traffic = BRACKETS_PATTERN.sub('', traffic).strip()

        # Print the cleaned traffic string
        str_traffic = len(traffic)
        print(traffic)
        print("String Length: " + str(str_traffic))

        if matches:
            for match in matches:
                lat_str, lon_str = match.split()
                # Ensure the latitude and longitude are correct length before converting
                if len(lat_str.split('.')[-1]) == 6 and len(lon_str.split('.')[-1]) == 6:
                    return float(lat_str), float(lon_str), traffic
            print("No latitude and longitude with sufficient precision found.")
            return None, None
        else:
            print("No latitude and longitude found.")
            return None, None
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None, None

if __name__ == "__main__":
    lat, lon, traffic = get_coordinates()
    if lat and lon:
        print(f"Latitude: {lat}, Longitude: {lon}")
