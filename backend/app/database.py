from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _database_url() -> str:
    host = os.getenv("DB_HOST_PSQL")
    if host:
        user = os.getenv("DB_USER_PSQL", "")
        password = os.getenv("DB_PASSWORD_PSQL", "")
        name = os.getenv("DB_NAME_PSQL", "")
        port = os.getenv("DB_PORT_PSQL", "5432")
        u = quote_plus(user)
        p = quote_plus(password)
        return f"postgresql://{u}:{p}@{host}:{port}/{name}"
    return os.getenv("DATABASE_URL", "sqlite:///./test.db")


def _normalize_postgres_url(url: str) -> str:
    """Render/Heroku-style postgres:// → postgresql:// for SQLAlchemy + ssl args."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


DATABASE_URL = _normalize_postgres_url(_database_url())

# Neon (and most cloud Postgres) require SSL; add sslmode if not present
_engine_args = {}
if DATABASE_URL.startswith("postgresql") and "sslmode" not in DATABASE_URL:
    _engine_args["connect_args"] = {"sslmode": "require"}

engine = create_engine(DATABASE_URL, **_engine_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def ensure_schema(engine) -> None:
    """Add columns/tables missing on older DB files (no Alembic in this project)."""
    from sqlalchemy import text

    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            try:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                    )
                )
            except Exception:
                pass
            for sql in (
                "ALTER TABLE users ADD COLUMN year_of_study INTEGER",
                "ALTER TABLE users ADD COLUMN department VARCHAR(120)",
                "ALTER TABLE users ADD COLUMN membership_tier VARCHAR(20)",
                "ALTER TABLE hostel_rooms ADD COLUMN eligibility_rules TEXT",
                "ALTER TABLE other_areas ADD COLUMN eligibility_rules TEXT",
                "ALTER TABLE bookings ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'normal'",
                "ALTER TABLE bookings ADD COLUMN created_at TIMESTAMP",
                "ALTER TABLE hostel_rooms ADD COLUMN staff_only BOOLEAN NOT NULL DEFAULT 0",
                "ALTER TABLE other_areas ADD COLUMN staff_only BOOLEAN NOT NULL DEFAULT 0",
            ):
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
            try:
                conn.execute(text("UPDATE bookings SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
            except Exception:
                pass
        elif dialect == "postgresql":
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
            for sql in (
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS year_of_study INTEGER",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(120)",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS membership_tier VARCHAR(20)",
                "ALTER TABLE hostel_rooms ADD COLUMN IF NOT EXISTS eligibility_rules JSONB",
                "ALTER TABLE other_areas ADD COLUMN IF NOT EXISTS eligibility_rules JSONB",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'normal'",
                "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE hostel_rooms ADD COLUMN IF NOT EXISTS staff_only BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE other_areas ADD COLUMN IF NOT EXISTS staff_only BOOLEAN NOT NULL DEFAULT FALSE",
            ):
                conn.execute(text(sql))
            conn.execute(
                text(
                    "UPDATE bookings SET created_at = NOW() AT TIME ZONE 'utc' WHERE created_at IS NULL"
                )
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
