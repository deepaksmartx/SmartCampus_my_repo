"""
Add dining_menu_items, facility_inventory_items; extend bookings; drop legacy JSON inventory on rooms/areas.

Run from backend directory:
  python migrations/migrate_facility_booking_extensions.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.database import engine, Base
from app import models


def _column_names(conn, table: str) -> set[str]:
    insp = inspect(conn)
    return {c["name"] for c in insp.get_columns(table)}


def _table_exists(conn, table: str) -> bool:
    return inspect(conn).has_table(table)


def run():
    dialect = engine.dialect.name
    Base.metadata.create_all(
        bind=engine,
        tables=[models.DiningMenuItem.__table__, models.FacilityInventoryItem.__table__],
    )
    print("ensure tables: dining_menu_items, facility_inventory_items")

    with engine.begin() as conn:

        cols = _column_names(conn, "bookings")
        if "meal_slot" not in cols:
            if dialect == "postgresql":
                conn.execute(text("ALTER TABLE bookings ADD COLUMN meal_slot VARCHAR(20)"))
            else:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN meal_slot VARCHAR(20)"))
            print("bookings: added meal_slot")
        if "dining_menu_item_ids" not in cols:
            if dialect == "postgresql":
                conn.execute(text("ALTER TABLE bookings ADD COLUMN dining_menu_item_ids JSONB"))
            else:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN dining_menu_item_ids JSON"))
            print("bookings: added dining_menu_item_ids")
        if "inventory_selections" not in cols:
            if dialect == "postgresql":
                conn.execute(text("ALTER TABLE bookings ADD COLUMN inventory_selections JSONB"))
            else:
                conn.execute(text("ALTER TABLE bookings ADD COLUMN inventory_selections JSON"))
            print("bookings: added inventory_selections")

        if _table_exists(conn, "hostel_rooms") and "inventory" in _column_names(conn, "hostel_rooms"):
            if dialect == "sqlite":
                try:
                    conn.execute(text("ALTER TABLE hostel_rooms DROP COLUMN inventory"))
                    print("hostel_rooms: dropped inventory")
                except Exception as e:
                    print(f"hostel_rooms: could not drop inventory ({e}); leave column unused")
            else:
                conn.execute(text("ALTER TABLE hostel_rooms DROP COLUMN IF EXISTS inventory"))
                print("hostel_rooms: dropped inventory")

        if _table_exists(conn, "other_areas") and "inventory" in _column_names(conn, "other_areas"):
            if dialect == "sqlite":
                try:
                    conn.execute(text("ALTER TABLE other_areas DROP COLUMN inventory"))
                    print("other_areas: dropped inventory")
                except Exception as e:
                    print(f"other_areas: could not drop inventory ({e}); leave column unused")
            else:
                conn.execute(text("ALTER TABLE other_areas DROP COLUMN IF EXISTS inventory"))
                print("other_areas: dropped inventory")

    print("migrate_facility_booking_extensions: done")


if __name__ == "__main__":
    run()
