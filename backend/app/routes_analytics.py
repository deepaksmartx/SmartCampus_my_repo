from __future__ import annotations
"""Facility utilization and booking statistics (Admin / Facility Manager)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models
from .database import get_db
from .auth import require_admin_or_facility_manager
from .schemas_iot import AnalyticsDashboard

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=AnalyticsDashboard)
def analytics_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    bookings_total = db.query(func.count(models.Booking.id)).scalar() or 0
    by_status = {}
    for st in models.BookingStatus:
        c = (
            db.query(func.count(models.Booking.id))
            .filter(models.Booking.status == st)
            .scalar()
            or 0
        )
        by_status[st.value] = c

    hostel_bc = (
        db.query(func.count(models.Booking.id))
        .filter(models.Booking.hostel_room_id.isnot(None))
        .scalar()
        or 0
    )
    oa_bc = (
        db.query(func.count(models.Booking.id))
        .filter(models.Booking.other_area_id.isnot(None))
        .scalar()
        or 0
    )
    rooms_n = db.query(func.count(models.HostelRoom.id)).scalar() or 0
    areas_n = db.query(func.count(models.OtherArea.id)).scalar() or 0

    readings_total = db.query(func.count(models.SensorReading.id)).scalar() or 0
    open_alerts = (
        db.query(func.count(models.SensorAlert.id))
        .filter(models.SensorAlert.status == models.AlertStatus.OPEN)
        .scalar()
        or 0
    )

    return AnalyticsDashboard(
        bookings_total=bookings_total,
        bookings_by_status=by_status,
        hostel_booking_count=hostel_bc,
        other_area_booking_count=oa_bc,
        hostel_rooms_count=rooms_n,
        other_areas_count=areas_n,
        sensor_readings=readings_total,
        open_sensor_alerts=open_alerts,
    )
