"""Add inventory JSON to hostel_rooms and other_areas. Run: python migrations/migrate_inventory_columns.py"""
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import text, inspect

from app.database import engine


def run() -> None:
    insp = inspect(engine)
    dialect = engine.dialect.name
    with engine.begin() as conn:
        cols_h = {c["name"] for c in insp.get_columns("hostel_rooms")}
        if "inventory" not in cols_h:
            if dialect == "postgresql":
                conn.execute(text("ALTER TABLE hostel_rooms ADD COLUMN inventory JSONB DEFAULT '{}'::jsonb"))
            else:
                conn.execute(text("ALTER TABLE hostel_rooms ADD COLUMN inventory JSON"))
            print("hostel_rooms: added inventory")
        else:
            print("hostel_rooms.inventory already exists, skipping")

        cols_o = {c["name"] for c in insp.get_columns("other_areas")}
        if "inventory" not in cols_o:
            if dialect == "postgresql":
                conn.execute(text("ALTER TABLE other_areas ADD COLUMN inventory JSONB DEFAULT '{}'::jsonb"))
            else:
                conn.execute(text("ALTER TABLE other_areas ADD COLUMN inventory JSON"))
            print("other_areas: added inventory")
        else:
            print("other_areas.inventory already exists, skipping")
    print("Migration complete.")


if __name__ == "__main__":
    run()
