"""
Add sensor_alerts.name_or_room_no (room no or area name snapshot for UI).

Backfill: first segment of facility_name before middle dot, when present.

Run from the backend directory:
  python migrations/migrate_sensor_alerts_name_or_room_no.py
"""
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import inspect, text

from app.database import engine


def run() -> None:
    insp = inspect(engine)
    if "sensor_alerts" not in insp.get_table_names():
        print("sensor_alerts missing.")
        return
    cols = {c["name"] for c in insp.get_columns("sensor_alerts")}
    if "name_or_room_no" in cols:
        print("name_or_room_no column already exists on sensor_alerts.")
        return
    if engine.dialect.name != "postgresql":
        print("Non-PostgreSQL: add name_or_room_no column manually if needed.")
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE sensor_alerts ADD COLUMN name_or_room_no VARCHAR(200) NULL"
            )
        )
        conn.execute(
            text(
                """
                UPDATE sensor_alerts
                SET name_or_room_no = NULLIF(TRIM(SPLIT_PART(facility_name, '·', 1)), '')
                WHERE facility_name IS NOT NULL
                  AND TRIM(facility_name) <> ''
                """
            )
        )
    print("Added sensor_alerts.name_or_room_no and backfilled from facility_name.")


if __name__ == "__main__":
    run()
