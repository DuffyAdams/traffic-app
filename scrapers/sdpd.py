# scrapers/sdpd.py
"""San Diego Police Department (SDPD) incident scraper."""

import hashlib
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import SDPD_SCRAPE_URL, HEADERS
from logger import safe_print


def scrape_sdpd_incidents():
    """Return a list of incident dicts from the SDPD online CAD table."""
    safe_print("Scraping SDPD incidents...")
    try:
        response = requests.get(SDPD_SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        soup  = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="myDataTable")
        if not table:
            safe_print("SDPD: No table found.")
            return []

        incidents = []
        for row in table.find("tbody").find_all("tr"):
            cols = [ele.text.strip() for ele in row.find_all("td")]
            if len(cols) < 5:
                continue

            dt_str, call_type, division, neighborhood, address = cols[:5]

            unique_str  = f"{dt_str}_{address}_{call_type}"
            incident_id = "SDPD-" + hashlib.md5(unique_str.encode()).hexdigest()[:8]

            try:
                dt_obj   = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                date_val = dt_obj.strftime("%Y-%m-%d")
                time_val = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                date_val = datetime.now().strftime("%Y-%m-%d")
                time_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            incidents.append({
                "No.":           incident_id,
                "Date":          date_val,
                "Timestamp":     time_val,
                "City":          "San Diego",
                "Neighborhood":  neighborhood,
                "Location":      address,
                "Location Desc.": division,
                "Type":          call_type,
                "Details":       [f"Division: {division}", f"Neighborhood: {neighborhood}"],
                "Source":        "SDPD",
            })

        safe_print(f"SDPD: Found {len(incidents)} incidents.")
        return incidents

    except Exception as e:
        safe_print(f"Error scraping SDPD: {e}")
        return []
