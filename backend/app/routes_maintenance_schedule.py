"""Planned maintenance scheduling (admin / facility manager)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from . import models
from .database import get_db
from .auth import require_admin_or_facility_manager, verify_token
from .schemas_maintenance_schedule import (
    MaintenanceScheduleCreate,
    MaintenanceScheduleUpdate,
    MaintenanceScheduleResponse,
)
from .services.notification_service import create_notification
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/maintenance/schedules", tags=["maintenance schedule"])


def _facility_label_and_detail(db: Session, row: models.MaintenanceSchedule) -> tuple[str, dict]:
    if row.hostel_room_id:
        hr = (
            row.hostel_room
            or db.query(models.HostelRoom)
            .options(
                joinedload(models.HostelRoom.building),
                joinedload(models.HostelRoom.facility_type),
            )
            .filter(models.HostelRoom.id == row.hostel_room_id)
            .first()
        )
        if not hr:
            return f"Hostel room #{row.hostel_room_id}", {"kind": "hostel_room", "id": row.hostel_room_id}
        b = hr.building.name if hr.building else None
        ft = hr.facility_type.name.value if hr.facility_type else None
        label = f"Room {hr.roomno}" + (f" · {b}" if b else "")
        return label, {
            "kind": "hostel_room",
            "id": hr.id,
            "roomno": hr.roomno,
            "room_type": hr.room_type.value if hasattr(hr.room_type, "value") else str(hr.room_type),
            "building": b,
            "facility_type": ft,
        }
    if row.other_area_id:
        oa = (
            row.other_area
            or db.query(models.OtherArea)
            .options(
                joinedload(models.OtherArea.building),
                joinedload(models.OtherArea.facility_type),
            )
            .filter(models.OtherArea.id == row.other_area_id)
            .first()
        )
        if not oa:
            return f"Area #{row.other_area_id}", {"kind": "other_area", "id": row.other_area_id}
        b = oa.building.name if oa.building else None
        ft = oa.facility_type.name.value if oa.facility_type else None
        label = oa.name + (f" · {b}" if b else "")
        return label, {
            "kind": "other_area",
            "id": oa.id,
            "name": oa.name,
            "building": b,
            "facility_type": ft,
        }
    return "—", {}


def _to_response(db: Session, row: models.MaintenanceSchedule) -> MaintenanceScheduleResponse:
    st = row.status
    status_str = st.value if hasattr(st, "value") else str(st)
    creator = row.creator
    cname = creator.name if creator else "—"
    label, detail = _facility_label_and_detail(db, row)
    return MaintenanceScheduleResponse(
        id=row.id,
        title=row.title,
        notes=row.notes,
        hostel_room_id=row.hostel_room_id,
        other_area_id=row.other_area_id,
        facility_label=label,
        facility_detail=detail,
        scheduled_start=row.scheduled_start,
        scheduled_end=row.scheduled_end,
        status=status_str,
        created_by_id=row.created_by_id,
        created_by_name=cname,
        created_at=row.created_at,
    )


def _check_and_notify_overlapping_bookings(db: Session, scheduled_start, scheduled_end, hostel_room_id, other_area_id):
    if hostel_room_id:
        overlapping_bookings = (
            db.query(models.Booking)
            .filter(
                models.Booking.hostel_room_id == hostel_room_id,
                models.Booking.status != models.BookingStatus.REJECTED,
                models.Booking.start_time < scheduled_end,
                models.Booking.end_time > scheduled_start,
            )
            .all()
        )
        ist = ZoneInfo("Asia/Kolkata")
        
        # Ensure the datetime has a timezone before converting. If naive, assume UTC.
        st_utc = scheduled_start if scheduled_start.tzinfo else scheduled_start.replace(tzinfo=ZoneInfo("UTC"))
        en_utc = scheduled_end if scheduled_end.tzinfo else scheduled_end.replace(tzinfo=ZoneInfo("UTC"))
        
        st_str = st_utc.astimezone(ist).strftime("%Y-%m-%d %H:%M:%S")
        en_str = en_utc.astimezone(ist).strftime("%Y-%m-%d %H:%M:%S")

        for b in overlapping_bookings:
            create_notification(
                db,
                b.user_id,
                "Maintenance Scheduled During Booking",
                f"Maintenance is scheduled from {st_str} to {en_str} during your booking."
            )
    elif other_area_id:
        overlapping = (
            db.query(models.Booking)
            .filter(
                models.Booking.other_area_id == other_area_id,
                models.Booking.status != models.BookingStatus.REJECTED,
                models.Booking.start_time < scheduled_end,
                models.Booking.end_time > scheduled_start,
            )
            .first()
        )
        if overlapping:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Maintenance schedule conflicts with an existing booking in this area.")


@router.get("", response_model=list[MaintenanceScheduleResponse])
def list_schedules(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    rows = (
        db.query(models.MaintenanceSchedule)
        .options(
            joinedload(models.MaintenanceSchedule.creator),
            joinedload(models.MaintenanceSchedule.hostel_room).options(
                joinedload(models.HostelRoom.building),
                joinedload(models.HostelRoom.facility_type),
            ),
            joinedload(models.MaintenanceSchedule.other_area).options(
                joinedload(models.OtherArea.building),
                joinedload(models.OtherArea.facility_type),
            ),
        )
        .order_by(models.MaintenanceSchedule.scheduled_start.desc())
        .limit(500)
        .all()
    )
    return [_to_response(db, r) for r in rows]


@router.post("", response_model=MaintenanceScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    body: MaintenanceScheduleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    if body.hostel_room_id:
        if not db.query(models.HostelRoom).filter(models.HostelRoom.id == body.hostel_room_id).first():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hostel room not found")
    else:
        if not db.query(models.OtherArea).filter(models.OtherArea.id == body.other_area_id).first():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Facility / area not found")

    if body.scheduled_end <= body.scheduled_start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="scheduled_end must be after scheduled_start")

    _check_and_notify_overlapping_bookings(
        db, 
        body.scheduled_start, 
        body.scheduled_end, 
        body.hostel_room_id, 
        body.other_area_id
    )

    row = models.MaintenanceSchedule(
        title=body.title.strip()[:200],
        notes=(body.notes or "").strip()[:4000] or None,
        hostel_room_id=body.hostel_room_id,
        other_area_id=body.other_area_id,
        scheduled_start=body.scheduled_start,
        scheduled_end=body.scheduled_end,
        status=models.MaintenanceScheduleStatus.SCHEDULED,
        created_by_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row = (
        db.query(models.MaintenanceSchedule)
        .options(
            joinedload(models.MaintenanceSchedule.creator),
            joinedload(models.MaintenanceSchedule.hostel_room).options(
                joinedload(models.HostelRoom.building),
                joinedload(models.HostelRoom.facility_type),
            ),
            joinedload(models.MaintenanceSchedule.other_area).options(
                joinedload(models.OtherArea.building),
                joinedload(models.OtherArea.facility_type),
            ),
        )
        .filter(models.MaintenanceSchedule.id == row.id)
        .first()
    )
    return _to_response(db, row)


@router.patch("/{schedule_id}", response_model=MaintenanceScheduleResponse)
def update_schedule(
    schedule_id: int,
    body: MaintenanceScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    row = db.query(models.MaintenanceSchedule).filter(models.MaintenanceSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        try:
            row.status = models.MaintenanceScheduleStatus(data["status"])
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        data.pop("status", None)
    for k in ("title", "notes", "scheduled_start", "scheduled_end"):
        if k in data and data[k] is not None:
            if k == "title":
                row.title = str(data[k]).strip()[:200]
            elif k == "notes":
                row.notes = str(data[k]).strip()[:4000] or None
            else:
                setattr(row, k, data[k])
    if row.scheduled_end <= row.scheduled_start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="scheduled_end must be after scheduled_start")

    if ("scheduled_start" in data and data["scheduled_start"] is not None) or ("scheduled_end" in data and data["scheduled_end"] is not None):
        _check_and_notify_overlapping_bookings(db, row.scheduled_start, row.scheduled_end, row.hostel_room_id, row.other_area_id)

    db.commit()
    db.refresh(row)
    row = (
        db.query(models.MaintenanceSchedule)
        .options(
            joinedload(models.MaintenanceSchedule.creator),
            joinedload(models.MaintenanceSchedule.hostel_room).options(
                joinedload(models.HostelRoom.building),
                joinedload(models.HostelRoom.facility_type),
            ),
            joinedload(models.MaintenanceSchedule.other_area).options(
                joinedload(models.OtherArea.building),
                joinedload(models.OtherArea.facility_type),
            ),
        )
        .filter(models.MaintenanceSchedule.id == schedule_id)
        .first()
    )
    return _to_response(db, row)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    row = db.query(models.MaintenanceSchedule).filter(models.MaintenanceSchedule.id == schedule_id).first()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    db.delete(row)
    db.commit()
    return None
