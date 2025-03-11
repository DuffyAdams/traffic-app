import requests
from bs4 import BeautifulSoup
import schedule
import time
import pprint
from termcolor import colored

# URL of the page to scrape
url = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"

# Store the previous data
previous_data = []

def scrape_table():
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Locate the table
    table = soup.find('table', id='gvIncidents')
    
    # Extract table headers
    headers = []
    for th in table.find_all('th'):
        headers.append(th.text.strip())
    
    # Extract table rows
    rows = []
    for tr in table.find_all('tr')[1:]:  # skip the header row
        cells = tr.find_all('td')
        row_data = [cell.text.strip() for cell in cells]
        rows.append(dict(zip(headers, row_data)))

    return rows

# Function to check for updates
def check_for_updates():
    global previous_data
    
    new_data = scrape_table()

    # Find the difference between previous and new data
    added_data = [item for item in new_data if item not in previous_data]
    removed_data = [item for item in previous_data if item not in new_data]
    
    # Print added and removed data with color coding
    if added_data:
        print(colored("New Data Added at " + time.strftime("%Y-%m-%d %H:%M:%S"), "green"))
        pprint.pprint(added_data)
    
    if removed_data:
        print(colored("Data Removed at " + time.strftime("%Y-%m-%d %H:%M:%S"), "red"))
        pprint.pprint(removed_data)

    # Update the previous data with the new data
    previous_data = new_data

# Schedule the check_for_updates function to run every 30 seconds
schedule.every(30).seconds.do(check_for_updates)

# Initial call to display the data immediately
check_for_updates()

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
