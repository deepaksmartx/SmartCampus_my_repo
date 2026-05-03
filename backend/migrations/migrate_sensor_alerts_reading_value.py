"""
Add sensor_alerts.reading_value (value at alert time).

Run from the backend directory:
  python migrations/migrate_sensor_alerts_reading_value.py
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
    if "reading_value" in cols:
        print("reading_value column already exists.")
        return
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE sensor_alerts ADD COLUMN reading_value VARCHAR(100) NULL")
            )
        print("Added sensor_alerts.reading_value")
    else:
        print("Non-PostgreSQL: add reading_value column manually if needed.")


if __name__ == "__main__":
    run()
