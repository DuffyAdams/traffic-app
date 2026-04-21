# monitor.py
"""
Background monitoring loop: orchestrates scraping, geocoding,
map generation, and final-description generation for inactive incidents.
"""

import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pytz
import requests

from config import (
    DB_FILE, MAP_GENERATOR, TARGET_DIR, TESTMODE, HEALTHCHECK_URL, db_lock
)
from logger import safe_print
from db import incident_exists, save_or_update_incident
from llm import generate_description
from geocoding import geocode_location as geo_geocode_location
from config import geo_cache


def geocode_location(location_query):
    """Geocode using the shared module and cache."""
    return geo_geocode_location(location_query, cache=geo_cache, debug_print=safe_print)


# ---------------------------------------------------------------------------
# Map generation
# ---------------------------------------------------------------------------

def run_map_generator(incident):
    """Generate a static map PNG for an incident and store the filename in-place."""
    incident_no = incident.get("No.") or incident.get("Incident No.", "unknown")
    if TESTMODE:
        safe_print(f"TESTMODE: Skipping map generation for {incident_no}")
        return
    if not os.path.exists(MAP_GENERATOR):
        safe_print(f"Map generator not found at '{MAP_GENERATOR}'.")
        return
    try:
        lon              = incident.get("Longitude")
        lat              = incident.get("Latitude")
        tz               = pytz.timezone("America/Los_Angeles")
        ts_str           = datetime.now(tz).strftime("%Y%m%d_%H%M%S_%f")
        filename         = os.path.join(TARGET_DIR, f"map_{incident_no}_{ts_str}.png")
        subprocess.run([sys.executable, MAP_GENERATOR, str(lon), str(lat), filename], check=True)
        safe_print(f"Map generated for {incident_no}.")
        incident["MapFilename"] = os.path.basename(filename)
    except subprocess.CalledProcessError as e:
        safe_print(f"Map generator error for {incident_no}: {e}")
    except Exception as e:
        safe_print(f"Unexpected map generator error for {incident_no}: {e}")


# ---------------------------------------------------------------------------
# Per-incident processing
# ---------------------------------------------------------------------------

def process_and_save_incident(incident):
    """Geocode, generate map, and persist one incident. Returns incident_no or None."""
    try:
        incident_no = incident.get("No.") or incident.get("Incident No.")
        if not incident_no:
            safe_print("WARNING: No incident number found. Skipping.")
            return None

        inc_exists  = incident_exists(incident_no, incident.get("Date", datetime.now().strftime("%Y-%m-%d")))
        needs_geocoding = not inc_exists

        if not needs_geocoding:
            with sqlite3.connect(DB_FILE, timeout=30) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT latitude, map_filename FROM incidents WHERE incident_no = ?",
                    (str(incident_no),),
                )
                row = cur.fetchone()
                if row and (row[0] is None or not row[1]):
                    safe_print(f"Incident {incident_no} missing coords/map — will geocode.")
                    needs_geocoding = True

        if needs_geocoding:
            _geocode_incident(incident)
            if "Latitude" in incident and "Longitude" in incident:
                run_map_generator(incident)

        save_or_update_incident(incident)
        return str(incident_no)
    except Exception as e:
        inc_id = incident.get("No.", "unknown") if isinstance(incident, dict) else "unknown"
        safe_print(f"Error processing incident {inc_id}: {e}")
        return None


def _geocode_incident(incident):
    """Attempt geocoding for sources that don't provide coordinates (SDPD/SDFD/SDSO)."""
    if "Latitude" in incident and "Longitude" in incident:
        return  # Already has coordinates (e.g. CHP)

    source       = incident.get("Source", "")
    location_str = incident.get("Location", "")

    if source == "SDPD":
        query = f"{location_str}, San Diego, CA"

    elif source == "SDFD":
        cross = incident.get("Location Desc.", "")
        if cross and cross != "N/A" and cross.lower() not in location_str.lower():
            query = f"{location_str} and {cross}, San Diego, CA"
        else:
            query = f"{location_str}, San Diego, CA"

    elif source == "SDSO":
        community = incident.get("Neighborhood", "")
        address   = location_str.replace("/", " & ")
        query     = f"{address}, {community}, CA" if community else f"{address}, San Diego County, CA"

    else:
        return

    safe_print(f"Geocoding {incident.get('No.')} ({source}): {query}")
    coords = geocode_location(query)
    if coords:
        incident.update(coords)


# ---------------------------------------------------------------------------
# Monitoring loop
# ---------------------------------------------------------------------------

def monitor_traffic_data(interval=15):
    """Continuously scrape all sources, process incidents, and manage active status."""
    # Import here to avoid circular dependency at module level
    from scrapers.chp  import scrape_chp_incidents
    from scrapers.sdpd import scrape_sdpd_incidents
    from scrapers.sdfd import scrape_sdfd_incidents
    from scrapers.sdso import scrape_sdso_incidents

    safe_print("Starting continuous traffic monitoring...")
    safe_print(f"DB: {DB_FILE}")
    safe_print(f"Maps: {TARGET_DIR}")
    safe_print("Press Ctrl+C to stop.")

    try:
        while True:
            try:
                safe_print(f"Checking updates... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # ── Parallel scraping ──────────────────────────────────────
                all_incidents = []
                scrapers = {
                    "CHP":  scrape_chp_incidents,
                    "SDPD": scrape_sdpd_incidents,
                    "SDFD": scrape_sdfd_incidents,
                    "SDSO": scrape_sdso_incidents,
                }
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(fn): name for name, fn in scrapers.items()}
                    for future in as_completed(futures):
                        name = futures[future]
                        try:
                            results = future.result()
                            all_incidents.extend(results)
                            safe_print(f"{name}: {len(results)} incidents fetched")
                        except Exception as e:
                            safe_print(f"Error scraping {name}: {e}")

                # ── Parallel processing ────────────────────────────────────
                active_ids = set()
                if all_incidents:
                    # CHP first (already has coords — faster to process)
                    all_incidents.sort(key=lambda x: 0 if x.get("Source") == "CHP" else 1)
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        futures = [executor.submit(process_and_save_incident, inc) for inc in all_incidents]
                        for f in as_completed(futures):
                            inc_id = f.result()
                            if inc_id:
                                active_ids.add(inc_id)
                else:
                    safe_print("No data retrieved from any source.")

                # ── Final descriptions for newly-inactive incidents ─────────
                _generate_final_descriptions(active_ids)

                # ── Mark stale incidents inactive ──────────────────────────
                _mark_inactive(active_ids)

                # ── Healthcheck ping ───────────────────────────────────────
                _ping_healthcheck(success=True)

            except Exception as e:
                safe_print(f"Error in monitoring loop: {e}")
                _ping_healthcheck(success=False)

            import time
            time.sleep(interval)

    except KeyboardInterrupt:
        safe_print("Monitoring stopped by user.")
    except Exception as e:
        safe_print(f"Fatal error: {e}")
        raise


def _generate_final_descriptions(active_ids):
    """Generate closing LLM summaries for incidents that just went inactive."""
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                cur.execute(
                    f"SELECT * FROM incidents WHERE active = 1 AND incident_no NOT IN ({placeholders})",
                    tuple(active_ids),
                )
            else:
                cur.execute("SELECT * FROM incidents WHERE active = 1")
            newly_inactive = [dict(row) for row in cur.fetchall()]

    if not newly_inactive:
        return

    safe_print(f"Generating final summaries for {len(newly_inactive)} newly inactive incidents...")

    def _process_final(record):
        try:
            details = json.loads(record.get("details", "[]") or "[]")
            if not details:
                return
            data = {
                "Neighborhood":  record.get("neighborhood"),
                "Location":      record.get("location"),
                "Location Desc.": record.get("location_desc"),
                "Type":          record.get("type"),
                "Details":       details,
            }
            final_desc, final_sev = generate_description(data)
            with db_lock:
                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                    conn.cursor().execute(
                        "UPDATE incidents SET description = ?, severity = ? WHERE incident_no = ? AND date = ?",
                        (final_desc, final_sev, record["incident_no"], record["date"]),
                    )
                    conn.commit()
        except Exception as ex:
            safe_print(f"Error generating final description for {record.get('incident_no')}: {ex}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in as_completed([executor.submit(_process_final, r) for r in newly_inactive]):
            pass


def _mark_inactive(active_ids):
    """Set active = 0 for incidents no longer in the current scrape."""
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cur = conn.cursor()
            if active_ids:
                placeholders = ",".join("?" for _ in active_ids)
                cur.execute(
                    f"UPDATE incidents SET active = 0 WHERE incident_no NOT IN ({placeholders})",
                    tuple(active_ids),
                )
            else:
                cur.execute("UPDATE incidents SET active = 0")
            conn.commit()


def _ping_healthcheck(success=True):
    url = HEALTHCHECK_URL + ("" if success else "/fail")
    try:
        requests.get(url, timeout=10)
        safe_print(f"Healthcheck ping: {'success' if success else 'failure'}")
    except Exception as e:
        safe_print(f"Failed to ping healthcheck: {e}")
