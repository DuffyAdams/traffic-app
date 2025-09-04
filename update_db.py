import sqlite3

DB_FILE = "/Users/duffyadams/Documents/traffic-app-repo/traffic-app/traffic_data.db"

def unify_collision_types():
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()

        # 1) normalize 'Trfc Collision...' into 'Traffic Collision'
        cur.execute("""
            UPDATE incidents
            SET type = 'Traffic Collision'
            WHERE type LIKE 'Trfc Collision%'
        """)
        cur.execute("SELECT changes()")
        trfc_fixed = cur.fetchone()[0]

        # 2) normalize anything starting with or containing 'Object Flying' into 'Debris From Vehicle'
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
