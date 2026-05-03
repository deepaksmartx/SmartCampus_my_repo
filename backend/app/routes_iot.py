from __future__ import annotations
"""IoT sensor ingestion (simulator / gateway) and monitoring APIs."""
import os
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

from . import models
from .database import get_db
from .auth import verify_token, require_admin_or_facility_manager, require_iot_dashboard_access
from .schemas_iot import (
    SensorIngest,
    SensorReadingResponse,
    SensorReadingEnriched,
    SensorAlertEnriched,
    AlertStatusUpdate,
    ThingsBoardSyncRequest,
)
from .services.iot_service import ingest_reading, get_alert_thresholds_for_api, is_occupancy_sensor_type
from .services.thingsboard_sync import sync_thingsboard_telemetry
from .services.iot_facility import (
    alert_name_or_room_from_info,
    resolve_facility,
    display_sensor_value,
    matches_facility_type_filter,
)

router = APIRouter(prefix="/iot", tags=["iot"])


def _security_occupancy_only(current_user: models.User) -> bool:
    """True only for Security users, regardless of enum/string role storage."""
    role = getattr(current_user, "role", None)
    if role is None:
        return False
    if isinstance(role, models.UserRole):
        return role == models.UserRole.SECURITY
    role_s = str(role).strip()
    return role_s in ("Security", "SECURITY", "UserRole.SECURITY")


def _ingest_key_ok(x_iot_key: str | None) -> bool:
    expected = os.getenv("IOT_INGEST_API_KEY", "").strip()
    return bool(expected) and x_iot_key == expected


@router.post("/ingest", response_model=SensorReadingResponse)
def ingest_sensor_data(
    body: SensorIngest,
    db: Session = Depends(get_db),
    x_iot_key: str | None = Header(None, alias="X-IoT-Key"),
):
    """
    Sensor simulator / API gateway posts readings here (protected by X-IoT-Key).
    """
    if not _ingest_key_ok(x_iot_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-IoT-Key")
    try:
        reading, _ = ingest_reading(
            db,
            body.facility_id,
            body.facility_scope,
            body.sensor_type,
            body.value,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return reading


@router.post("/thingsboard/sync", response_model=list[SensorReadingResponse])
def sync_thingsboard(
    body: ThingsBoardSyncRequest | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    """
    Pull latest telemetry from ThingsBoard (tenant REST + timeseries API), map into SensorReading,
    and persist. Configure THINGSBOARD_* env vars; optionally pass device_ids / device_names in body.
    """
    req = body or ThingsBoardSyncRequest()
    try:
        rows = sync_thingsboard_telemetry(
            db,
            device_ids=req.device_ids,
            device_names=req.device_names,
            telemetry_keys=req.telemetry_keys,
            value_key=req.value_key,
            lookback_ms=req.lookback_ms,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return rows


@router.get("/readings", response_model=list[SensorReadingEnriched])
def list_sensor_readings(
    limit: int = Query(200, ge=1, le=2000),
    facility_scope: str | None = None,
    facility_type_filter: str | None = Query(
        None,
        description="all | hostel | mens_hostel | ladies_hostel | dining | sports | academic_spaces",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_iot_dashboard_access),
):
    q = db.query(models.SensorReading).order_by(models.SensorReading.timestamp.desc())
    if facility_scope in ("hostel_room", "other_area"):
        q = q.filter(models.SensorReading.facility_scope == facility_scope)
    fetch_limit = min(limit * 5, 2000)
    rows = q.limit(fetch_limit).all()
    out: list[SensorReadingEnriched] = []
    for r in rows:
        db_fn = ((r.facility_name or "").strip() if getattr(r, "facility_name", None) else "")
        if db_fn in ("0", "00"):
            db_fn = ""
        info = resolve_facility(db, r.facility_id, r.facility_scope, db_fn or None)
        if not matches_facility_type_filter(
            info["facility_type_key"], r.facility_scope, facility_type_filter
        ):
            continue
        if _security_occupancy_only(current_user) and not is_occupancy_sensor_type(r.sensor_type):
            continue
        display_name = db_fn or info["facility_name"]
        out.append(
            SensorReadingEnriched(
                id=r.id,
                facility_id=r.facility_id,
                facility_scope=r.facility_scope,
                sensor_type=r.sensor_type,
                value=r.value,
                display_value=display_sensor_value(r.sensor_type, r.value),
                timestamp=r.timestamp,
                facility_name=display_name,
                facility_type_key=info["facility_type_key"],
                facility_detail=info["facility_detail"],
            )
        )
        if len(out) >= limit:
            break
    return out


@router.get("/alerts", response_model=list[SensorAlertEnriched])
def list_sensor_alerts(
    status_filter: str | None = Query(None, description="open | acknowledged | resolved | all"),
    limit: int = Query(100, ge=1, le=500),
    facility_type_filter: str | None = Query(
        None,
        description="all | hostel | mens_hostel | ladies_hostel | dining | sports | academic_spaces",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_iot_dashboard_access),
):
    q = db.query(models.SensorAlert).order_by(models.SensorAlert.triggered_at.desc())
    if status_filter and status_filter != "all":
        sf = status_filter.lower()
        if sf == "open":
            q = q.filter(models.SensorAlert.status == models.AlertStatus.OPEN)
        elif sf == "acknowledged":
            q = q.filter(models.SensorAlert.status == models.AlertStatus.ACKNOWLEDGED)
        elif sf == "resolved":
            q = q.filter(models.SensorAlert.status == models.AlertStatus.RESOLVED)
    fetch_limit = min(limit * 5, 1000)
    rows = q.limit(fetch_limit).all()
    out: list[SensorAlertEnriched] = []
    for a in rows:
        stored = (getattr(a, "facility_name", None) or "").strip()
        if stored in ("0", "00"):
            stored = ""
        stored_opt = stored or None
        info = resolve_facility(db, a.facility_id, a.facility_scope, stored_opt)
        if not matches_facility_type_filter(
            info["facility_type_key"], a.facility_scope, facility_type_filter
        ):
            continue
        if _security_occupancy_only(current_user) and not is_occupancy_sensor_type(a.sensor_type):
            continue
        st = a.status
        status_str = st.value if hasattr(st, "value") else str(st)
        rv = getattr(a, "reading_value", None)
        display_name = stored or info["facility_name"]
        nm_col = (getattr(a, "name_or_room_no", None) or "").strip()
        name_or_room = nm_col or alert_name_or_room_from_info(info, stored_opt) or None
        out.append(
            SensorAlertEnriched(
                id=a.id,
                facility_id=a.facility_id,
                facility_scope=a.facility_scope,
                sensor_type=a.sensor_type,
                alert_type=a.alert_type,
                triggered_at=a.triggered_at,
                status=status_str,
                reading_value=rv,
                display_value=display_sensor_value(a.sensor_type, rv or "")
                if rv is not None
                else None,
                facility_name=display_name,
                name_or_room_no=name_or_room,
                facility_type_key=info["facility_type_key"],
                facility_detail=info["facility_detail"],
            )
        )
        if len(out) >= limit:
            break
    return out


@router.patch("/alerts/{alert_id}", response_model=SensorAlertEnriched)
def update_alert_status(
    alert_id: int,
    body: AlertStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    alert = db.query(models.SensorAlert).filter(models.SensorAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if body.status == "acknowledged":
        alert.status = models.AlertStatus.ACKNOWLEDGED
    else:
        alert.status = models.AlertStatus.RESOLVED
    db.commit()
    db.refresh(alert)
    stored = (getattr(alert, "facility_name", None) or "").strip()
    if stored in ("0", "00"):
        stored = ""
    stored_opt = stored or None
    info = resolve_facility(db, alert.facility_id, alert.facility_scope, stored_opt)
    st = alert.status
    status_str = st.value if hasattr(st, "value") else str(st)
    rv = getattr(alert, "reading_value", None)
    display_name = stored or info["facility_name"]
    nm_col = (getattr(alert, "name_or_room_no", None) or "").strip()
    name_or_room = nm_col or alert_name_or_room_from_info(info, stored_opt) or None
    return SensorAlertEnriched(
        id=alert.id,
        facility_id=alert.facility_id,
        facility_scope=alert.facility_scope,
        sensor_type=alert.sensor_type,
        alert_type=alert.alert_type,
        triggered_at=alert.triggered_at,
        status=status_str,
        reading_value=rv,
        display_value=display_sensor_value(alert.sensor_type, rv or "")
        if rv is not None
        else None,
        facility_name=display_name,
        name_or_room_no=name_or_room,
        facility_type_key=info["facility_type_key"],
        facility_detail=info["facility_detail"],
    )


@router.get("/summary")
def iot_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_iot_dashboard_access),
):
    """Quick occupancy / latest readings counts for dashboard."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    if _security_occupancy_only(current_user):
        readings = (
            db.query(models.SensorReading)
            .filter(models.SensorReading.timestamp >= since)
            .all()
        )
        last24 = sum(1 for r in readings if is_occupancy_sensor_type(r.sensor_type))
        alerts = db.query(models.SensorAlert).filter(models.SensorAlert.status == models.AlertStatus.OPEN).all()
        open_alerts = sum(1 for a in alerts if is_occupancy_sensor_type(a.sensor_type))
        return {
            "readings_last_24h": last24,
            "open_alerts": open_alerts,
            "alert_thresholds": get_alert_thresholds_for_api(),
            "security_occupancy_only": True,
        }
    last24 = (
        db.query(func.count(models.SensorReading.id))
        .filter(models.SensorReading.timestamp >= since)
        .scalar()
        or 0
    )
    open_alerts = (
        db.query(func.count(models.SensorAlert.id))
        .filter(models.SensorAlert.status == models.AlertStatus.OPEN)
        .scalar()
        or 0
    )
    return {
        "readings_last_24h": last24,
        "open_alerts": open_alerts,
        "alert_thresholds": get_alert_thresholds_for_api(),
        "security_occupancy_only": False,
    }
