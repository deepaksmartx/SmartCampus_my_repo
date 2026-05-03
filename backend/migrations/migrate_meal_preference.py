"""Add bookings.meal_preference column. Run: python migrate_meal_preference.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from app.database import engine


def run():
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("bookings")}
    if "meal_preference" in cols:
        print("bookings.meal_preference already exists, skipping")
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE bookings ADD COLUMN meal_preference VARCHAR(20)"))
    print("Added bookings.meal_preference")


if __name__ == "__main__":
    run()
