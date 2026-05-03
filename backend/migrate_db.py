# Run this file to migrate/update the database schema
# This will drop existing tables and recreate them with the new schema

from app.database import engine, Base
from app import models
from sqlalchemy import text

def migrate():
    print("Connecting to Neon PostgreSQL...")
    
    # Create a connection
    with engine.begin() as connection:
        # Drop existing tables to recreate them with the new schema
        print("Dropping existing tables...")
        try:
            connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))
            print("✅ Dropped existing tables")
        except Exception as e:
            print(f"⚠️ Error dropping tables: {e}")
    
    # Create all tables with the new schema
    print("Creating tables with new schema...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully with new schema!")
    print("Tables created:", list(Base.metadata.tables.keys()))

if __name__ == "__main__":
    migrate()
