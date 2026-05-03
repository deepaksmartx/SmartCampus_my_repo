"""
Create tables for room allocations, IoT (sensor readings / alerts), and in-app notifications.

Matches models: RoomAllocation, SensorReading, SensorAlert, Notification.

Run from the backend directory:
  python migrations/migrate_room_allocations_iot_notifications.py

Safe to run multiple times: skips tables that already exist.
"""
import os
import sys

# backend/ must be on path for `app`
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import inspect

from app.database import Base, engine
from app import models


def run() -> None:
    insp = inspect(engine)
    existing = set(insp.get_table_names())

    specs = [
        ("room_allocations", models.RoomAllocation.__table__),
        ("sensor_readings", models.SensorReading.__table__),
        ("sensor_alerts", models.SensorAlert.__table__),
        ("notifications", models.Notification.__table__),
    ]

    to_create = [t for name, t in specs if name not in existing]
    for name, _ in specs:
        if name in existing:
            print(f"{name}: already exists, skipping")

    if to_create:
        Base.metadata.create_all(bind=engine, tables=to_create)
        print("Created tables:", ", ".join(t.name for t in to_create))
    else:
        print("All target tables already present.")

    print("Migration complete.")


if __name__ == "__main__":
    run()
