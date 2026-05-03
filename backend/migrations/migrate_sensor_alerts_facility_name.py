"""
Add sensor_alerts.facility_name (label copied from reading at alert time).

Run from the backend directory:
  python migrations/migrate_sensor_alerts_facility_name.py
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
    if "facility_name" in cols:
        print("facility_name column already exists on sensor_alerts.")
        return
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE sensor_alerts ADD COLUMN facility_name VARCHAR(200) NULL")
            )
        print("Added sensor_alerts.facility_name")
    else:
        print("Non-PostgreSQL: add facility_name column manually if needed.")


if __name__ == "__main__":
    run()
