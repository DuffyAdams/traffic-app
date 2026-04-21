# db.py
"""
Database initialisation and all CRUD operations for the traffic app.
"""

import json
import sqlite3
from datetime import datetime

from config import DB_FILE, db_lock
from logger import safe_print
from llm import generate_description


# ---------------------------------------------------------------------------
# Schema & migrations
# ---------------------------------------------------------------------------

def init_db():
    """Initialize SQLite database schema and run any pending migrations."""
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")   # Better concurrent read/write
        conn.execute("PRAGMA synchronous=NORMAL")  # Balanced durability/speed
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        # ── Core tables ────────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_no       TEXT,
                date              TEXT,
                timestamp         TEXT,
                city              TEXT,
                neighborhood      TEXT,
                location          TEXT,
                location_desc     TEXT,
                type              TEXT,
                details           TEXT,
                description       TEXT,
                latitude          REAL,
                longitude         REAL,
                map_filename      TEXT,
                likes             INTEGER DEFAULT 0,
                comments          TEXT DEFAULT '[]',
                active            INTEGER DEFAULT 1,
                source            TEXT DEFAULT 'CHP',
                PRIMARY KEY (incident_no, date)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                device_uuid  TEXT,
                incident_no  TEXT,
                timestamp    TEXT,
                PRIMARY KEY (device_uuid, incident_no)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid TEXT,
                incident_no TEXT,
                username    TEXT,
                comment     TEXT,
                timestamp   TEXT
            )
        """)

        # ── Migrations (safe ALTER TABLE with fallback) ────────────────────
        _add_column(cur, "incidents", "source",           "TEXT DEFAULT 'CHP'")
        _add_column(cur, "incidents", "geocode_precision", "TEXT DEFAULT 'unknown'")
        _add_column(cur, "incidents", "severity",          "INTEGER DEFAULT NULL")

        # ── Type normalisation ─────────────────────────────────────────────
        _normalise_types(cur)

        # ── Indexes ────────────────────────────────────────────────────────
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_active    ON incidents(active)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_date      ON incidents(date)")

        conn.commit()


def _add_column(cur, table, column, definition):
    """Safely add a column; ignore if it already exists."""
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except sqlite3.OperationalError:
        pass  # Column already exists


def _normalise_types(cur):
    """Standardise legacy type names in the incidents table."""
    mappings = [
        ("type LIKE 'Trfc Collision%'",            "Traffic Collision"),
        ("type = 'Assist CT with Maintenance'",    "Maintenance"),
        ("type = 'Road/Weather Conditions'",       "Road Conditions"),
        ("type = 'Object Flying From Veh'",        "Debris from Vehicle"),
        ("type = 'Assist with Construction'",      "Construction"),
    ]
    for condition, new_type in mappings:
        cur.execute(f"UPDATE incidents SET type = ? WHERE {condition}", (new_type,))

    cur.execute("DELETE FROM incidents WHERE type = 'Request CalTrans Notify'")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_incidents(
    limit=20,
    incident_types=None,
    locations=None,
    sources=None,
    active_only=False,
    cursor=None,
    date_filter=None,
):
    """Fetch incidents with optional filtering, cursor-based pagination, and embedded comments."""
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        conditions, params = [], []

        if sources:
            _in(conditions, params, "source", sources)
        if incident_types:
            _in(conditions, params, "type", incident_types)
        if locations:
            _in(conditions, params, "location", locations)
        if active_only:
            conditions.append("active = 1")
        if date_filter in ("day", "daily"):
            conditions.append("date = ?")
            params.append(datetime.now().strftime("%Y-%m-%d"))
        if cursor:
            if "|" in cursor:
                ts_part, id_part = cursor.split("|", 1)
                conditions.append("(timestamp, incident_no) < (?, ?)")
                params.extend([ts_part, id_part])
            else:
                conditions.append("timestamp < ?")
                params.append(cursor)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM incidents{where} ORDER BY timestamp DESC, incident_no DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, tuple(params))
        incidents = [dict(row) for row in cur.fetchall()]

        if incidents:
            _attach_comments(cur, incidents)

        return incidents


def _in(conditions, params, column, values):
    placeholders = ",".join("?" for _ in values)
    conditions.append(f"{column} IN ({placeholders})")
    params.extend(values)


def _attach_comments(cur, incidents):
    """Join comments onto each incident dict in-place."""
    incident_nos = [inc["incident_no"] for inc in incidents]
    placeholders = ",".join("?" for _ in incident_nos)
    cur.execute(
        f"SELECT incident_no, username, comment, timestamp "
        f"FROM comments WHERE incident_no IN ({placeholders}) ORDER BY timestamp ASC",
        tuple(incident_nos),
    )
    by_incident = {}
    for row in cur.fetchall():
        by_incident.setdefault(row[0], []).append(
            {"username": row[1] or "Anonymous", "comment": row[2], "timestamp": row[3]}
        )
    for inc in incidents:
        inc["comments"] = by_incident.get(inc["incident_no"], [])
        try:
            inc["Details"] = json.loads(inc["details"]) if inc["details"] else []
        except Exception:
            inc["Details"] = []


def incident_exists(incident_no, date):
    """Return True if an incident already exists in the DB."""
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM incidents WHERE incident_no = ? AND date = ?",
            (str(incident_no), date),
        )
        return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_or_update_incident(data):
    """Insert a new incident or update an existing one. Returns True if a change was made."""
    if not data:
        return False

    incident_no = data.get("No.") or data.get("Incident No.")
    if not incident_no:
        safe_print("No incident number found in data.")
        return False

    date            = data.get("Date",      datetime.now().strftime("%Y-%m-%d"))
    new_timestamp   = data.get("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    city            = data.get("City", "")
    neighborhood    = data.get("Neighborhood", "")
    location        = data.get("Location", "")
    location_desc   = data.get("Location Desc.", "")
    source          = data.get("Source", "CHP")
    geocode_precision = data.get("precision", "unknown")
    latitude        = data.get("Latitude")
    longitude       = data.get("Longitude")
    new_map_filename = data.get("MapFilename", "")
    active_status   = data.get("active", 1)

    # Standardise type
    type_field = data.get("Type", "")
    if type_field and type_field.startswith("Trfc Collision"):
        type_field = "Traffic Collision"

    new_details = data.get("Details", [])
    if isinstance(new_details, str):
        new_details = [new_details]
    details_json = json.dumps(new_details)

    # ── Fetch existing record (outside db_lock – read-only) ────────────────
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT details, description, severity FROM incidents WHERE incident_no = ? AND date = ?",
                (str(incident_no), date),
            )
            existing = cur.fetchone()

    # ── Generate LLM description outside the lock (slow network call) ──────
    if not existing:
        new_description, new_severity = generate_description(data)
    else:
        new_description = existing["description"]
        new_severity    = existing["severity"]

    # ── Apply DB update/insert ─────────────────────────────────────────────
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM incidents WHERE incident_no = ? AND date = ?",
                (str(incident_no), date),
            )
            existing_record = cur.fetchone()

            if existing_record:
                existing_data = dict(existing_record)
                updates, params = [], []

                if details_json != existing_data.get("details", ""):
                    updates.append("details = ?, description = ?")
                    params.extend([details_json, new_description])
                if latitude and latitude != existing_data.get("latitude"):
                    updates.append("latitude = ?")
                    params.append(latitude)
                if longitude and longitude != existing_data.get("longitude"):
                    updates.append("longitude = ?")
                    params.append(longitude)
                if geocode_precision != "unknown" and geocode_precision != existing_data.get("geocode_precision"):
                    updates.append("geocode_precision = ?")
                    params.append(geocode_precision)
                if new_map_filename and new_map_filename != existing_data.get("map_filename"):
                    updates.append("map_filename = ?")
                    params.append(new_map_filename)

                if updates:
                    updates.append("active = ?")
                    query = f"UPDATE incidents SET {', '.join(updates)} WHERE incident_no = ? AND date = ?"
                    params.extend([active_status, str(incident_no), date])
                    cur.execute(query, tuple(params))
                    conn.commit()
                    safe_print(f"Incident {incident_no} updated.")
                    return True
                else:
                    safe_print(f"No changes for incident {incident_no}.")
                    return False
            else:
                cur.execute(
                    """
                    INSERT INTO incidents
                    (incident_no, date, timestamp, city, neighborhood, location, location_desc, type,
                     details, description, latitude, longitude, map_filename, likes, comments,
                     active, source, geocode_precision, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(incident_no), date, new_timestamp, city, neighborhood,
                        location, location_desc, type_field, details_json, new_description,
                        latitude, longitude, new_map_filename, 0, "[]",
                        active_status, source, geocode_precision, new_severity,
                    ),
                )
                conn.commit()
                safe_print(f"Incident {incident_no} inserted.")
                return True
