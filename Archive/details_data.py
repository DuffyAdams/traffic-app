import logging
import requests
from bs4 import BeautifulSoup


url = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"

try:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    row = soup.find('tr', class_='gvRow')
    if row:
        data = [td.get_text(strip=True) for td in row.find_all('td')]
        data.pop(0)  # Remove the 'Details' link text
        print(" ".join(data))
    else:
        logging.warning("No data row found in the response")
        print(None)
except Exception as e:
    logging.error(f"Error in fetch_traffic_data: {e}")
    print(None)