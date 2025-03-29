import sqlite3

DB_FILE = "traffic_data.db"  # Adjust path if needed

def unify_collision_types():
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        # This query updates all rows where 'type' starts with 'Trfc Collision'
        cur.execute("""
            UPDATE incidents
            SET type = 'Traffic Collision'
            WHERE type LIKE 'Trfc Collision%'
        """)
        conn.commit()

if __name__ == "__main__":
    unify_collision_types()
    print("Updated collision types in the database.")
