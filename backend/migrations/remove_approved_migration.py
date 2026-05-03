"""
Remove 'approved' column from hostel_rooms and other_areas.
Run from backend directory:
  python migrations/remove_approved_migration.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text, inspect
from app.database import engine

def run():
    dialect = engine.dialect.name
    with engine.begin() as conn:
        insp = inspect(conn)
        
        # hostel_rooms
        cols_h = {c["name"] for c in insp.get_columns("hostel_rooms")}
        if "approved" in cols_h:
            if dialect == "sqlite":
                print("hostel_rooms: Column drop not directly supported in SQLite via ALTER. Re-run migrate_db.py if needed, or leave column unused.")
            else:
                conn.execute(text("ALTER TABLE hostel_rooms DROP COLUMN IF EXISTS approved"))
                print("hostel_rooms: dropped approved")
        
        # other_areas
        cols_o = {c["name"] for c in insp.get_columns("other_areas")}
        if "approved" in cols_o:
            if dialect == "sqlite":
                print("other_areas: Column drop not directly supported in SQLite via ALTER. Re-run migrate_db.py if needed, or leave column unused.")
            else:
                conn.execute(text("ALTER TABLE other_areas DROP COLUMN IF EXISTS approved"))
                print("other_areas: dropped approved")

    print("remove_approved_migration: done")

if __name__ == "__main__":
    run()
