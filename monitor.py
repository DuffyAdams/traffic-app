# monitor.py
"""
Background monitoring loop: orchestrates scraping, geocoding,
incident persistence, and description generation.
"""

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import requests

from config import (
    BATCH_LLM_ENABLED,
    BATCH_LLM_INTERVAL_SECONDS,
    BATCH_LLM_MAX_ITEMS,
    BATCH_LLM_MODEL,
    DB_FILE,
    HEALTHCHECK_URL,
    HTTP_TIMEOUT_SECONDS,
    SDSO_API_URL,
    db_lock,
    geo_cache,
    now_pst,
    pst_date_str,
    pst_timestamp_str,
)
from db import fetch_existing_incidents, save_or_update_incident
from geocoding import geocode_location as geo_geocode_location
from llm import generate_batch_descriptions, generate_description
from logger import safe_print
from runtime_metrics import record_scrape_success
from sqlite_utils import sqlite_connection


_description_executor = ThreadPoolExecutor(max_workers=2)
_batch_executor = ThreadPoolExecutor(max_workers=1)
_batch_future = None
_batch_retry_after = 0.0


def geocode_location(location_query):
    """Geocode using the shared module and cache."""
    return geo_geocode_location(location_query, cache=geo_cache, debug_print=safe_print)


# ---------------------------------------------------------------------------
# Per-incident processing
# ---------------------------------------------------------------------------

def process_and_save_incident(incident, existing_record=None):
    """Geocode and persist one incident. Return its ID, or ``None`` on failure."""
    try:
        incident_no = incident.get("No.") or incident.get("Incident No.")
        if not incident_no:
            safe_print("WARNING: No incident number found. Skipping.")
            return None

        inc_exists = existing_record is not None
        needs_geocoding = not inc_exists

        if not inc_exists:
            # Write the row immediately so the feed can surface it without waiting
            # for geocoding or description enrichment to finish.
            save_or_update_incident(
                incident,
                existing_record=None,
                generate_description_on_insert=False,
            )
            _description_executor.submit(_refresh_incident_description, dict(incident))

        if inc_exists and (
            existing_record.get("latitude") is None
            or existing_record.get("longitude") is None
        ):
            safe_print(f"Incident {incident_no} is missing coordinates; will geocode.")
            needs_geocoding = True

        if needs_geocoding:
            _geocode_incident(incident)

        save_or_update_incident(
            incident,
            existing_record=existing_record if inc_exists else None,
            generate_description_on_insert=False,
        )
        return str(incident_no)
    except Exception as e:
        inc_id = incident.get("No.", "unknown") if isinstance(incident, dict) else "unknown"
        safe_print(f"Error processing incident {inc_id}: {e}")
        return None


def _geocode_incident(incident):
    """Attempt geocoding for sources that don't provide coordinates (SDPD/SDFD/SDSO)."""
    if (
        incident.get("Latitude") is not None
        and incident.get("Longitude") is not None
    ):
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
        query = (
            f"{address}, {community}, CA"
            if community
            else f"{address}, San Diego County, CA"
        )

    elif source == "CHP":
        query = f"{location_str}, San Diego County, CA" if location_str else "San Diego County, CA"

    else:
        return

    safe_print(f"Geocoding {incident.get('No.')} ({source}): {query}")
    coords = geocode_location(query)
    if coords:
        incident.update(coords)


def _refresh_incident_description(incident):
    """Generate a summary for a newly inserted incident without blocking ingest."""
    try:
        incident_no = incident.get("No.") or incident.get("Incident No.")
        if not incident_no:
            return

        description, severity = generate_description(incident)
        incident_date = incident.get("Date", pst_date_str())

        with db_lock:
            with sqlite_connection(DB_FILE) as conn:
                conn.cursor().execute(
                    """
                    UPDATE incidents
                    SET description = ?, severity = ?
                    WHERE incident_no = ? AND date = ?
                      AND batch_enriched_at IS NULL
                    """,
                    (description, severity, str(incident_no), incident_date),
                )
                conn.commit()
    except Exception as e:
        safe_print(
            f"Background description refresh failed for {incident.get('No.', 'unknown')}: {e}"
        )


# ---------------------------------------------------------------------------
# Monitoring loop
# ---------------------------------------------------------------------------

def _default_scrapers():
    """Build the source-to-scraper mapping for configured feeds."""
    from scrapers.chp import scrape_chp_incidents
    from scrapers.sdfd import scrape_sdfd_incidents
    from scrapers.sdpd import scrape_sdpd_incidents
    from scrapers.sdso import scrape_sdso_incidents

    scrapers = {
        "CHP": scrape_chp_incidents,
        "SDPD": scrape_sdpd_incidents,
        "SDFD": scrape_sdfd_incidents,
    }
    if SDSO_API_URL:
        scrapers["SDSO"] = scrape_sdso_incidents
    return scrapers


def run_monitor_cycle(scrapers=None):
    """Run one complete scrape cycle and return its elapsed time.

    Stale-incident cleanup only runs for a source when both its scrape and all
    of its incident-processing tasks succeeded. A transient failure therefore
    cannot incorrectly clear that source's live incidents.
    """
    cycle_start = time.perf_counter()
    safe_print(f"Checking updates... {now_pst().strftime('%Y-%m-%d %H:%M:%S')}")

    scrapers = scrapers or _default_scrapers()
    all_incidents = []
    successful_sources = set()

    with ThreadPoolExecutor(max_workers=max(1, len(scrapers))) as executor:
        futures = {executor.submit(scraper): source for source, scraper in scrapers.items()}
        for future in as_completed(futures):
            source = futures[future]
            try:
                incidents = future.result()
                if not isinstance(incidents, list):
                    raise TypeError("scraper returned a non-list result")
                for incident in incidents:
                    incident.setdefault("Source", source)
                all_incidents.extend(incidents)
                successful_sources.add(source)
                safe_print(f"{source}: {len(incidents)} incidents fetched")
            except Exception as exc:
                safe_print(f"Error scraping {source}: {exc}")

    if not successful_sources:
        raise RuntimeError("All configured traffic sources failed")

    active_ids_by_source = {source: set() for source in successful_sources}
    failed_processing_sources = set()

    if all_incidents:
        all_incidents.sort(key=lambda item: 0 if item.get("Source") == "CHP" else 1)
        incident_keys = [
            (
                incident.get("No.") or incident.get("Incident No."),
                incident.get("Date", pst_date_str()),
            )
            for incident in all_incidents
        ]
        existing_records = fetch_existing_incidents(incident_keys)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for incident in all_incidents:
                incident_no = incident.get("No.") or incident.get("Incident No.")
                incident_date = incident.get("Date", pst_date_str())
                existing_record = existing_records.get((str(incident_no), incident_date))
                future = executor.submit(
                    process_and_save_incident,
                    incident,
                    existing_record,
                )
                futures[future] = incident.get("Source", "CHP")

            for future in as_completed(futures):
                source = futures[future]
                try:
                    incident_id = future.result()
                except Exception as exc:
                    safe_print(f"Error processing {source} incident: {exc}")
                    incident_id = None
                if incident_id:
                    active_ids_by_source[source].add(incident_id)
                else:
                    failed_processing_sources.add(source)
    else:
        safe_print("All successful source feeds are currently empty.")

    for source in failed_processing_sources:
        active_ids_by_source.pop(source, None)

    _generate_final_descriptions(active_ids_by_source)
    _mark_inactive(active_ids_by_source)
    _submit_batch_refinement_if_due()
    return time.perf_counter() - cycle_start


def monitor_traffic_data(interval=15):
    """Continuously run scrape cycles until the process is interrupted."""
    safe_print("Starting continuous traffic monitoring...")
    safe_print(f"DB: {DB_FILE}")
    safe_print("Press Ctrl+C to stop.")

    try:
        while True:
            try:
                elapsed = run_monitor_cycle()
                _ping_healthcheck(success=True)
                record_scrape_success(elapsed)
            except Exception as exc:
                safe_print(f"Error in monitoring loop: {exc}")
                _ping_healthcheck(success=False)
            time.sleep(interval)
    except KeyboardInterrupt:
        safe_print("Monitoring stopped by user.")


def _generate_final_descriptions(active_ids_by_source):
    """Generate closing LLM summaries for incidents that just went inactive."""
    if not active_ids_by_source:
        return

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            sources = tuple(active_ids_by_source)
            placeholders = ",".join("?" for _ in sources)
            rows = conn.execute(
                f"SELECT * FROM incidents WHERE active = 1 AND source IN ({placeholders})",
                sources,
            ).fetchall()

    newly_inactive = [
        dict(row)
        for row in rows
        if row["incident_no"] not in active_ids_by_source[row["source"]]
    ]

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
                with sqlite_connection(DB_FILE) as conn:
                    conn.cursor().execute(
                        """
                        UPDATE incidents
                        SET description = ?, severity = ?, batch_queued_at = ?,
                            batch_enriched_at = NULL
                        WHERE incident_no = ? AND date = ?
                        """,
                        (
                            final_desc,
                            final_sev,
                            pst_timestamp_str(),
                            record["incident_no"],
                            record["date"],
                        ),
                    )
                    conn.commit()
        except Exception as ex:
            safe_print(f"Error generating final description for {record.get('incident_no')}: {ex}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in as_completed([executor.submit(_process_final, r) for r in newly_inactive]):
            pass


# ---------------------------------------------------------------------------
# Deferred batch refinement
# ---------------------------------------------------------------------------

def _submit_batch_refinement_if_due():
    """Start one eligible LLM batch without blocking the monitor loop."""
    global _batch_future, _batch_retry_after

    if not BATCH_LLM_ENABLED:
        return

    if _batch_future is not None:
        if not _batch_future.done():
            return
        try:
            _batch_future.result()
        except Exception as exc:
            safe_print(f"Batch LLM refinement failed: {exc}")
            _batch_retry_after = time.monotonic() + min(
                BATCH_LLM_INTERVAL_SECONDS, 300
            )
        finally:
            _batch_future = None

    if time.monotonic() < _batch_retry_after:
        return

    cutoff = pst_timestamp_str(
        now_pst() - timedelta(seconds=BATCH_LLM_INTERVAL_SECONDS)
    )
    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            oldest = conn.execute(
                """
                SELECT MIN(batch_queued_at)
                FROM incidents
                WHERE batch_queued_at IS NOT NULL
                  AND batch_enriched_at IS NULL
                """
            ).fetchone()[0]
            if not oldest or oldest > cutoff:
                return

            rows = conn.execute(
                """
                SELECT *
                FROM incidents
                WHERE batch_queued_at IS NOT NULL
                  AND batch_enriched_at IS NULL
                  AND batch_queued_at <= ?
                ORDER BY batch_queued_at, timestamp, incident_no
                LIMIT ?
                """,
                (cutoff, BATCH_LLM_MAX_ITEMS),
            ).fetchall()

    if not rows:
        return

    records = [dict(row) for row in rows]
    safe_print(
        f"Submitting {len(records)} incidents to {BATCH_LLM_MODEL} "
        "for batch refinement."
    )
    _batch_future = _batch_executor.submit(_refine_description_batch, records)


def _refine_description_batch(records):
    """Generate and atomically apply a validated batch of smarter summaries."""
    results = generate_batch_descriptions(records)
    enriched_at = pst_timestamp_str()
    updated = 0

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            cur = conn.cursor()
            for result in results:
                record = records[result["item_id"] - 1]
                cur.execute(
                    """
                    UPDATE incidents
                    SET description = ?, severity = ?, batch_enriched_at = ?
                    WHERE incident_no = ? AND date = ?
                      AND batch_queued_at = ?
                      AND batch_enriched_at IS NULL
                    """,
                    (
                        result["summary"],
                        result["severity"],
                        enriched_at,
                        record["incident_no"],
                        record["date"],
                        record["batch_queued_at"],
                    ),
                )
                updated += cur.rowcount
            conn.commit()

    safe_print(
        f"Batch LLM refinement applied to {updated}/{len(records)} incidents."
    )


def _mark_inactive(active_ids_by_source):
    """Deactivate stale incidents for sources with fully successful cycles."""
    if not active_ids_by_source:
        return

    with db_lock:
        with sqlite_connection(DB_FILE) as conn:
            cur = conn.cursor()
            for source, active_ids in active_ids_by_source.items():
                if active_ids:
                    placeholders = ",".join("?" for _ in active_ids)
                    cur.execute(
                        f"""
                        UPDATE incidents
                        SET active = 0
                        WHERE source = ? AND incident_no NOT IN ({placeholders})
                        """,
                        (source, *active_ids),
                    )
                else:
                    cur.execute(
                        "UPDATE incidents SET active = 0 WHERE source = ?",
                        (source,),
                    )
            conn.commit()


def _ping_healthcheck(success=True):
    if not HEALTHCHECK_URL:
        return
    url = HEALTHCHECK_URL + ("" if success else "/fail")
    try:
        requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        safe_print(f"Healthcheck ping: {'success' if success else 'failure'}")
    except Exception as e:
        safe_print(f"Failed to ping healthcheck: {e}")
