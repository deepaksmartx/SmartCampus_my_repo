"""Create maintenance_tickets table. Run: python migrations/migrate_maintenance_tickets.py"""
import os
import sys

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_ROOT)

from sqlalchemy import inspect

from app.database import Base, engine
from app import models


def run() -> None:
    insp = inspect(engine)
    if "maintenance_tickets" in insp.get_table_names():
        print("maintenance_tickets: already exists, skipping")
        return
    Base.metadata.create_all(bind=engine, tables=[models.MaintenanceTicket.__table__])
    print("Created table: maintenance_tickets")
    print("Migration complete.")


if __name__ == "__main__":
    run()
