"""
Migrate bookings.approved (bool) -> bookings.status (pending|accepted|rejected).
Run once: python migrate_booking_status.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from app.database import engine


def run():
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("bookings")}
    if "status" in cols:
        print("bookings.status already exists, skipping migration")
        return
    if "approved" not in cols:
        print("No approved column; schema may be new. If INSERT fails, recreate tables.")
        return
    with engine.begin() as conn:
        dialect = engine.dialect.name
        if dialect == "postgresql":
            conn.execute(text("ALTER TABLE bookings ADD COLUMN status VARCHAR(20)"))
            conn.execute(text(
                "UPDATE bookings SET status = CASE WHEN approved THEN 'accepted' ELSE 'pending' END"
            ))
            conn.execute(text("ALTER TABLE bookings ALTER COLUMN status SET NOT NULL"))
            conn.execute(text("ALTER TABLE bookings ALTER COLUMN status SET DEFAULT 'pending'"))
            conn.execute(text("ALTER TABLE bookings DROP COLUMN approved"))
        else:
            # SQLite: limited ALTER
            conn.execute(text("ALTER TABLE bookings ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"))
            conn.execute(text(
                "UPDATE bookings SET status = CASE WHEN approved THEN 'accepted' ELSE 'pending' END"
            ))
            print("SQLite: added status column; SQLite cannot DROP approved easily — use recreate or ignore old column")
        print("Migrated bookings: approved -> status")


if __name__ == "__main__":
    run()
