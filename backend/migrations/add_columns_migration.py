"""
Add new columns to existing tables (hostel_rooms, other_areas, bookings).
Run once: python add_columns_migration.py
Safe to run multiple times - skips if columns already exist.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

def col_exists(err):
    s = str(err).lower()
    return "already exists" in s or "duplicate" in s

def run():
    with engine.begin() as conn:
        # hostel_rooms: add building_id, floor_id, approved
        for col, sql in [
            ("building_id", "ALTER TABLE hostel_rooms ADD COLUMN building_id INTEGER REFERENCES buildings(id)"),
            ("floor_id", "ALTER TABLE hostel_rooms ADD COLUMN floor_id INTEGER REFERENCES floors(id)"),
            ("approved", "ALTER TABLE hostel_rooms ADD COLUMN approved BOOLEAN NOT NULL DEFAULT FALSE"),
        ]:
            try:
                conn.execute(text(sql))
                print(f"hostel_rooms: added {col}")
            except Exception as e:
                if col_exists(e):
                    print(f"hostel_rooms.{col} already exists, skipping")
                else:
                    raise

        # other_areas: rename requires_approval -> approved (or add approved if needed)
        try:
            conn.execute(text("ALTER TABLE other_areas RENAME COLUMN requires_approval TO approved"))
            print("other_areas: renamed requires_approval -> approved")
        except Exception as e:
            err = str(e).lower()
            if "does not exist" in err:
                try:
                    conn.execute(text("ALTER TABLE other_areas ADD COLUMN approved BOOLEAN NOT NULL DEFAULT FALSE"))
                    print("other_areas: added approved")
                except Exception as e2:
                    if col_exists(e2):
                        print("other_areas.approved already exists, skipping")
                    else:
                        raise
            elif col_exists(e):
                print("other_areas.approved already exists, skipping")
            else:
                raise

        # bookings: add approved
        try:
            conn.execute(text("ALTER TABLE bookings ADD COLUMN approved BOOLEAN NOT NULL DEFAULT FALSE"))
            print("bookings: added approved")
        except Exception as e:
            if col_exists(e):
                print("bookings.approved already exists, skipping")
            else:
                raise
    print("Migration complete.")

if __name__ == "__main__":
    run()
