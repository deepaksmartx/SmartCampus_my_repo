# Run this file ONCE to create all tables in your Neon PostgreSQL database
# Command: python init_db.py

from app.database import engine, Base
from app import models  # This import ensures all models are registered with Base

def init():
    print("Connecting to Neon PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")
    print("Tables created:", list(Base.metadata.tables.keys()))

if __name__ == "__main__":
    init()
