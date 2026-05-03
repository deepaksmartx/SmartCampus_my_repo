from __future__ import annotations
"""Process simulated sensor readings, detect abnormal values, create alerts."""
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import delete

from .. import models
from .notification_service import notify_sensor_alert


def _threshold(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_alert_thresholds_for_api() -> dict[str, float | str]:
    """Exposed on GET /iot/summary for dashboard copy (matches evaluate_abnormal rules)."""
    return {
        "water_high_liters": _threshold("IOT_THRESHOLD_WATER", 200),
        "energy_high_kwh": _threshold("IOT_THRESHOLD_ENERGY", 800),
        "temp_high_c": _threshold("IOT_THRESHOLD_TEMP", 40),
        "temp_low_c": _threshold("IOT_THRESHOLD_TEMP_LOW", -5),
        "occupancy_note": "Values must be 0 or 1",
    }


def is_occupancy_sensor_type(sensor_type: str) -> bool:
    st = (sensor_type or "").lower().strip()
    if st in ("occupancy", "pir", "motion"):
        return True
    if "occupancy" in st.replace(" ", ""):
        return True
    return False


def _normalize_incoming_value(sensor_type: str, value: str) -> str:
    """Store occupancy as '0' or '1' (integer semantics)."""
    if is_occupancy_sensor_type(sensor_type):
        try:
            return str(int(round(float(value))))
        except (TypeError, ValueError):
            return value
    return value


def evaluate_abnormal(sensor_type: str, value: str) -> str | None:
    st = (sensor_type or "").lower().strip()
    if is_occupancy_sensor_type(sensor_type or ""):
        try:
            vi = int(round(float(value)))
        except (TypeError, ValueError):
            return "invalid_numeric_value"
        if vi not in (0, 1):
            return "occupancy_out_of_range"
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "invalid_numeric_value"
    if st in ("energy", "energy_kwh", "energy_usage", "power_kw") or (
        "energy" in st and "meter" in st
    ):
        if v > _threshold("IOT_THRESHOLD_ENERGY", 800):
            return "high_energy"
    elif st in ("water", "water_l", "water_liters", "water_usage") or (
        "water" in st and "meter" in st
    ):
        if v > _threshold("IOT_THRESHOLD_WATER", 200):
            return "high_water_usage"
    elif st in ("temp", "temperature", "temp_c"):
        if v > _threshold("IOT_THRESHOLD_TEMP", 40) or v < _threshold("IOT_THRESHOLD_TEMP_LOW", -5):
            return "temperature_anomaly"
    return None


def ingest_reading(
    db: Session,
    facility_id: int,
    facility_scope: str,
    sensor_type: str,
    value: str,
) -> tuple[models.SensorReading, models.SensorAlert | None]:
    if facility_scope not in ("hostel_room", "other_area"):
        raise ValueError("facility_scope must be hostel_room or other_area")
    st_low = sensor_type.lower().strip()
    if facility_scope == "hostel_room" and st_low in ("occupancy", "pir", "motion"):
        raise ValueError("Occupancy sensors are not used for hostel rooms")
    value = _normalize_incoming_value(sensor_type, value)
    reading = models.SensorReading(
        facility_id=facility_id,
        facility_scope=facility_scope,
        sensor_type=sensor_type,
        value=value,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(reading)
    db.flush()

    alert_obj = None
    abnormal = evaluate_abnormal(sensor_type, value)
    if abnormal:
        from .iot_facility import alert_name_or_room_from_info, resolve_facility

        stored_label = (getattr(reading, "facility_name", None) or "").strip()
        info = resolve_facility(db, facility_id, facility_scope, stored_label or None)
        alert_label = stored_label or info["facility_name"]
        nm = alert_name_or_room_from_info(info, stored_label or None)
        alert_obj = models.SensorAlert(
            facility_id=facility_id,
            facility_scope=facility_scope,
            sensor_type=sensor_type,
            alert_type=abnormal,
            reading_value=value,
            facility_name=alert_label or None,
            name_or_room_no=nm,
            triggered_at=datetime.now(timezone.utc),
            status=models.AlertStatus.OPEN,
        )
        db.add(alert_obj)
        db.flush()
        notify_sensor_alert(
            db,
            alert_obj,
            f"Reading value={value!r} triggered rule {abnormal}.",
        )
    else:
        db.commit()
    db.refresh(reading)
    if alert_obj:
        db.refresh(alert_obj)
    return reading, alert_obj


def persist_thingsboard_reading(
    db: Session,
    *,
    facility_id: int,
    facility_scope: str,
    facility_name: str | None,
    sensor_type: str,
    value: str,
    timestamp: datetime,
    thingsboard_device_id: str | None,
    thingsboard_ts: int | None,
) -> models.SensorReading:
    """Store a reading from ThingsBoard (scope may be a TB facility_type label, not hostel_room)."""
    if thingsboard_device_id and thingsboard_ts is not None:
        existing = (
            db.query(models.SensorReading)
            .filter(
                models.SensorReading.thingsboard_device_id == thingsboard_device_id,
                models.SensorReading.thingsboard_ts == thingsboard_ts,
            )
            .first()
        )
        if existing:
            return existing

    value = _normalize_incoming_value(sensor_type, value)
    reading = models.SensorReading(
        facility_id=facility_id,
        facility_scope=facility_scope,
        facility_name=facility_name,
        sensor_type=sensor_type,
        value=value,
        timestamp=timestamp,
        thingsboard_device_id=thingsboard_device_id,
        thingsboard_ts=thingsboard_ts,
    )
    db.add(reading)
    db.flush()

    alert_obj = None
    abnormal = evaluate_abnormal(sensor_type, value)
    if abnormal:
        from .iot_facility import alert_name_or_room_from_info, resolve_facility

        stored_label = (facility_name or "").strip()
        info = resolve_facility(db, facility_id, facility_scope, stored_label or None)
        alert_label = stored_label or info["facility_name"]
        nm = alert_name_or_room_from_info(info, stored_label or None)
        alert_obj = models.SensorAlert(
            facility_id=facility_id,
            facility_scope=facility_scope,
            sensor_type=sensor_type,
            alert_type=abnormal,
            reading_value=value,
            facility_name=alert_label or None,
            name_or_room_no=nm,
            triggered_at=timestamp,
            status=models.AlertStatus.OPEN,
        )
        db.add(alert_obj)
        db.flush()
        notify_sensor_alert(
            db,
            alert_obj,
            f"Reading value={value!r} triggered rule {abnormal}.",
        )
    else:
        db.commit()
    db.refresh(reading)
    if alert_obj:
        db.refresh(alert_obj)
    return reading


def purge_readings_older_than_days(db: Session, days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = db.execute(
        delete(models.SensorReading).where(models.SensorReading.timestamp < cutoff)
    )
    db.commit()
    return result.rowcount or 0
