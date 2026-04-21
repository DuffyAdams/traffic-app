# scrapers/chp.py
"""
California Highway Patrol (CHP) incident scraper.
Fetches live incidents from the CAD dispatch feed.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from config import CHP_SCRAPE_URL, HEADERS, PARAMS
from logger import safe_print

# ── Pre-compiled patterns ──────────────────────────────────────────────────
_VIEWSTATE_PATTERN = re.compile(
    r'<input\s+type="hidden"\s+name="__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]+)"\s*/?>'
)
_LAT_LON_PATTERN  = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
_EXCLUDED_DETAILS = {"Unit At Scene", "Unit Enroute", "Unit Assigned"}


def scrape_chp_incidents():
    """Return a list of incident dicts from the CHP live CAD feed."""
    try:
        response = requests.get(CHP_SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        soup     = BeautifulSoup(response.text, "html.parser")
        table    = soup.find("table", id="gvIncidents")
        if not table:
            safe_print("CHP: No incident table found.")
            return []

        headers   = [th.get_text(strip=True) for th in table.find_all("th")]
        rows      = table.find_all("tr")[1:]  # Skip header
        viewstate = _get_viewstate(response.text)
        if not viewstate:
            safe_print("CHP: No __VIEWSTATE found.")
            return []

        incidents_list = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_process_row, idx, row, headers, viewstate)
                for idx, row in enumerate(rows)
            ]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    incidents_list.append(result)

        return incidents_list
    except Exception as e:
        safe_print("Error scraping CHP incidents:", e)
        return []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_viewstate(html_text):
    match = _VIEWSTATE_PATTERN.search(html_text)
    return match.group(1) if match else None


def _get_incident_details(row_index, viewstate):
    """POST to CHP site to retrieve lat/lon and timeline details for one row."""
    try:
        data = {
            "__LASTFOCUS":          "",
            "__EVENTTARGET":        "gvIncidents",
            "__EVENTARGUMENT":      f"Select${row_index}",
            "__VIEWSTATE":          viewstate,
            "__VIEWSTATEGENERATOR": "B13DF00D",
            "ddlComCenter":         "BCCC",
            "ddlSearches":          "Choose One",
            "ddlResources":         "Choose One",
        }
        post = requests.post(CHP_SCRAPE_URL, params=PARAMS, headers=HEADERS, data=data)
        post.raise_for_status()
        return _extract_traffic_info(post.text)
    except requests.exceptions.RequestException as e:
        safe_print(f"CHP: Network error for row {row_index}: {e}")
        return {}
    except Exception as e:
        safe_print(f"CHP: Unexpected error for row {row_index}: {e}")
        return {}


def _extract_traffic_info(response_text):
    """Parse lat/lon and detail timeline from CHP HTML response."""
    matches = _LAT_LON_PATTERN.findall(response_text)
    soup    = BeautifulSoup(response_text, "html.parser")
    details_table = soup.find("table", id="tblDetails")
    details = []

    if details_table:
        for row in details_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 3:
                time_cell   = cells[0].get_text(strip=True)
                detail_cell = cells[-1].get_text(strip=True) if cells[-1].get("colspan") else ""
                if detail_cell and not any(ex in detail_cell for ex in _EXCLUDED_DETAILS):
                    details.append(f"[{time_cell}] {detail_cell}" if time_cell else detail_cell)

    if matches:
        for match in matches:
            lat_str, lon_str = match.split()
            if len(lat_str.split(".")[-1]) == 6 and len(lon_str.split(".")[-1]) == 6:
                return {"Latitude": float(lat_str), "Longitude": float(lon_str), "Details": details}
    return {}


def _process_row(idx, row, headers, viewstate):
    row_data = [cell.get_text(strip=True) for cell in row.find_all("td")]
    if "Location" in headers and row_data[headers.index("Location")] == "Media Log":
        return None

    table_data         = dict(zip(headers, row_data))
    additional_details = _get_incident_details(idx, viewstate)
    if not additional_details:
        safe_print(f"CHP WARNING: No details for row {idx}. Skipping.")
        return None

    merged   = {**table_data, **additional_details}
    chp_time = table_data.get("Time", "")

    if chp_time:
        try:
            now       = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            try:
                dt_obj = datetime.strptime(f"{today_str} {chp_time}", "%Y-%m-%d %I:%M %p")
            except ValueError:
                dt_obj = datetime.strptime(f"{today_str} {chp_time}", "%Y-%m-%d %H:%M")

            if dt_obj > now + timedelta(minutes=5):
                dt_obj -= timedelta(days=1)

            merged["Timestamp"] = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            merged["Date"]      = dt_obj.strftime("%Y-%m-%d")
        except Exception as e:
            safe_print(f"CHP: Time parse error '{chp_time}': {e}")
            now = datetime.now()
            merged["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
            merged["Date"]      = now.strftime("%Y-%m-%d")
    else:
        now = datetime.now()
        merged["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
        merged["Date"]      = now.strftime("%Y-%m-%d")

    merged["Source"] = "CHP"
    return merged
