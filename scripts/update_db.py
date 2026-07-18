from contextlib import closing
from pathlib import Path
import sqlite3

DB_FILE = Path(__file__).resolve().parents[1] / "traffic_data.db"

def unify_collision_types():
    with closing(sqlite3.connect(DB_FILE)) as conn:
        cur = conn.cursor()

        # 1) normalize 'Trfc Collision...' into 'Traffic Collision'
        cur.execute("""
            UPDATE incidents
            SET type = 'Traffic Collision'
            WHERE type LIKE 'Trfc Collision%'
        """)
        cur.execute("SELECT changes()")
        trfc_fixed = cur.fetchone()[0]

        # Normalize legacy "Object Flying" labels into "Debris From Vehicle".
        cur.execute("""
            UPDATE incidents
            SET type = 'Debris From Vehicle'
            WHERE LOWER(type) LIKE '%object flying%'
               OR LOWER(type) LIKE '%flying%';
        """)
        cur.execute("SELECT changes()")
        flying_fixed = cur.fetchone()[0]

        conn.commit()

    return trfc_fixed, flying_fixed

if __name__ == "__main__":
    trfc_fixed, flying_fixed = unify_collision_types()
    print(f"Updated 'Trfc Collision*' -> 'Traffic Collision': {trfc_fixed} rows")
    print(f"Updated types containing 'Flying' -> 'Debris From Vehicle': {flying_fixed} rows")
