# scrapers/sdfd.py
"""San Diego Fire Department (SDFD) incident scraper."""

import hashlib
from datetime import datetime

import requests

from config import SDFD_API_URL, HEADERS
from logger import safe_print


def scrape_sdfd_incidents():
    """Return a list of incident dicts from the SDFD dispatch API."""
    safe_print("Scraping SDFD incidents...")
    try:
        response = requests.get(SDFD_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        incidents = []
        for item in data:
            # Prefer the richer ResponseDate (ISO 8601); fall back to ResponseDateString
            dt_str      = item.get("ResponseDate", "") or item.get("ResponseDateString", "")
            call_type   = item.get("CallType", "")
            address     = item.get("Address", "")
            cross_street = item.get("CrossStreet", "")
            units       = item.get("Units", [])
            unit_codes  = [u.get("Code") for u in units] if units else []

            unique_str  = f"{dt_str}_{address}_{call_type}"
            incident_id = "SDFD-" + hashlib.md5(unique_str.encode()).hexdigest()[:8]

            try:
                if "T" in dt_str:
                    dt_obj = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
                else:
                    dt_obj = datetime.strptime(" ".join(dt_str.split()), "%Y-%m-%d %H:%M")
                date_val = dt_obj.strftime("%Y-%m-%d")
                time_val = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                safe_print(f"SDFD: Date parse error for '{dt_str}': {e}")
                date_val = datetime.now().strftime("%Y-%m-%d")
                time_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            details = []
            if cross_street:
                details.append(f"Cross Street: {cross_street}")
            if unit_codes:
                details.append(f"Units: {', '.join(unit_codes)}")

            incidents.append({
                "No.":           incident_id,
                "Date":          date_val,
                "Timestamp":     time_val,
                "City":          "San Diego",
                "Neighborhood":  "",
                "Location":      address,
                "Location Desc.": cross_street,
                "Type":          call_type,
                "Details":       details,
                "Source":        "SDFD",
            })

        safe_print(f"SDFD: Found {len(incidents)} incidents.")
        return incidents

    except Exception as e:
        safe_print(f"Error scraping SDFD: {e}")
        return []
