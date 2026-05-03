"""
Add ThingsBoard-related columns to sensor_readings; widen facility_scope.

Run from the backend directory:
  python migrations/migrate_sensor_readings_thingsboard.py
"""
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import inspect, text

from app.database import engine


def _postgres() -> bool:
    return engine.dialect.name == "postgresql"


def run() -> None:
    insp = inspect(engine)
    table_names = set(insp.get_table_names())
    if "sensor_readings" not in table_names:
        print("sensor_readings missing; run migrate_room_allocations_iot_notifications first.")
        return

    cols = {c["name"] for c in insp.get_columns("sensor_readings")}

    with engine.begin() as conn:
        if _postgres():
            conn.execute(
                text("ALTER TABLE sensor_readings ALTER COLUMN facility_scope TYPE VARCHAR(200)")
            )
            if "sensor_alerts" in table_names:
                conn.execute(
                    text("ALTER TABLE sensor_alerts ALTER COLUMN facility_scope TYPE VARCHAR(200)")
                )
            if "facility_name" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE sensor_readings ADD COLUMN facility_name VARCHAR(200) NULL"
                    )
                )
            if "thingsboard_device_id" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE sensor_readings ADD COLUMN thingsboard_device_id VARCHAR(80) NULL"
                    )
                )
            if "thingsboard_ts" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE sensor_readings ADD COLUMN thingsboard_ts BIGINT NULL"
                    )
                )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_sensor_readings_tb_device_ts "
                    "ON sensor_readings (thingsboard_device_id, thingsboard_ts)"
                )
            )
        else:
            print(
                "Non-PostgreSQL dialect: apply equivalent ALTERs manually if needed.",
            )

    print("ThingsBoard sensor_readings migration complete.")


if __name__ == "__main__":
    run()
