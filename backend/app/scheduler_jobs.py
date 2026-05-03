from __future__ import annotations
"""Scheduled jobs: sensor data retention (30 days)."""
import logging
from app.database import SessionLocal
from app.services.iot_service import purge_readings_older_than_days

logger = logging.getLogger(__name__)


def run_sensor_retention_job() -> None:
    db = SessionLocal()
    try:
        n = purge_readings_older_than_days(db, days=30)
        logger.info("Sensor retention: removed %s readings older than 30 days", n)
    except Exception as e:
        logger.exception("Sensor retention job failed: %s", e)
    finally:
        db.close()
