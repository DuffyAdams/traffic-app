# scrapers/sdpd.py
"""San Diego Police Department (SDPD) incident scraper."""

import hashlib
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import SDPD_SCRAPE_URL, HEADERS, HTTP_TIMEOUT_SECONDS
from config import ensure_pst, now_pst
from logger import safe_print
from scrapers import ScraperError


def _looks_like_datetime(value):
    if not value:
        return False

    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue

    return False


def _extract_sdpd_columns(cols):
    """Normalize SDPD table rows across known layouts."""
    if len(cols) < 5:
        return None

    # Current layout includes a leading empty control/details column:
    # ["", datetime, call type, division, neighborhood, block address]
    if len(cols) >= 6 and not cols[0] and _looks_like_datetime(cols[1]):
        dt_str, call_type, division, neighborhood, address = cols[1:6]
        # Preserve the historically-generated ID shape to avoid duplicate
        # active SDPD rows after the scraper fix lands.
        unique_str = f"_{division}_{dt_str}"
        return dt_str, call_type, division, neighborhood, address, unique_str

    # Fallback for a plain five-column layout with no control column.
    if _looks_like_datetime(cols[0]):
        dt_str, call_type, division, neighborhood, address = cols[:5]
        unique_str = f"{dt_str}_{address}_{call_type}"
        return dt_str, call_type, division, neighborhood, address, unique_str

    # Defensive fallback if SDPD changes the DOM again but keeps datetime in col 1.
    if len(cols) >= 6 and _looks_like_datetime(cols[1]):
        dt_str, call_type, division, neighborhood, address = cols[1:6]
        unique_str = f"{dt_str}_{address}_{call_type}"
        return dt_str, call_type, division, neighborhood, address, unique_str

    return None


def scrape_sdpd_incidents():
    """Return a list of incident dicts from the SDPD online CAD table."""
    safe_print("Scraping SDPD incidents...")
    try:
        response = requests.get(SDPD_SCRAPE_URL, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        soup  = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="myDataTable")
        if not table:
            raise ScraperError("SDPD incident table was not present")

        body = table.find("tbody")
        if body is None:
            raise ScraperError("SDPD incident table did not contain a body")

        incidents = []
        for row in body.find_all("tr"):
            cols = [ele.text.strip() for ele in row.find_all("td")]
            parsed = _extract_sdpd_columns(cols)
            if not parsed:
                continue

            dt_str, call_type, division, neighborhood, address, unique_str = parsed

            incident_id = "SDPD-" + hashlib.md5(unique_str.encode()).hexdigest()[:8]

            try:
                dt_obj   = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                dt_obj   = ensure_pst(dt_obj)
                date_val = dt_obj.strftime("%Y-%m-%d")
                time_val = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                date_val = now_pst().strftime("%Y-%m-%d")
                time_val = now_pst().strftime("%Y-%m-%d %H:%M:%S")

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

    except ScraperError:
        raise
    except Exception as exc:
        raise ScraperError(f"SDPD scrape failed: {exc}") from exc
