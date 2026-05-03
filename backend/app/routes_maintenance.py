"""Maintenance issues: report broken assets (photos) and track status."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from . import models
from .database import get_db
from .auth import verify_token, require_admin_or_facility_manager
from .schemas_maintenance import MaintenanceTicketResponse, MaintenanceTicketStatusUpdate

router = APIRouter(prefix="/maintenance", tags=["maintenance issue"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads" / "maintenance"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILES = 6
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB each


def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _facility_label_and_detail(
    db: Session, ticket: models.MaintenanceTicket
) -> tuple[str, dict]:
    if ticket.hostel_room_id:
        hr = (
            ticket.hostel_room
            or db.query(models.HostelRoom)
            .options(
                joinedload(models.HostelRoom.building),
                joinedload(models.HostelRoom.facility_type),
            )
            .filter(models.HostelRoom.id == ticket.hostel_room_id)
            .first()
        )
        if not hr:
            return f"Hostel room #{ticket.hostel_room_id}", {"kind": "hostel_room", "id": ticket.hostel_room_id}
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
    if ticket.other_area_id:
        oa = (
            ticket.other_area
            or db.query(models.OtherArea)
            .options(
                joinedload(models.OtherArea.building),
                joinedload(models.OtherArea.facility_type),
            )
            .filter(models.OtherArea.id == ticket.other_area_id)
            .first()
        )
        if not oa:
            return f"Area #{ticket.other_area_id}", {"kind": "other_area", "id": ticket.other_area_id}
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


def _ticket_to_response(db: Session, t: models.MaintenanceTicket) -> MaintenanceTicketResponse:
    label, detail = _facility_label_and_detail(db, t)
    st = t.status
    status_str = st.value if hasattr(st, "value") else str(st)
    paths = t.photo_paths if isinstance(t.photo_paths, list) else []
    urls = [p if isinstance(p, str) and p.startswith("/") else f"/{p}" for p in paths]
    rep = t.reporter
    rname = rep.name if rep else "—"
    return MaintenanceTicketResponse(
        id=t.id,
        title=t.title,
        description=t.description,
        status=status_str,
        hostel_room_id=t.hostel_room_id,
        other_area_id=t.other_area_id,
        facility_label=label,
        facility_detail=detail,
        photo_urls=urls,
        reporter_id=t.reporter_id,
        reporter_name=rname,
        created_at=t.created_at,
    )


@router.get("/tickets", response_model=list[MaintenanceTicketResponse])
def list_tickets(
    status_filter: str | None = Query(None, description="open | in_progress | resolved | closed | all"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    q = db.query(models.MaintenanceTicket).options(
        joinedload(models.MaintenanceTicket.reporter),
        joinedload(models.MaintenanceTicket.hostel_room),
        joinedload(models.MaintenanceTicket.other_area),
    )
    if current_user.role not in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER):
        q = q.filter(models.MaintenanceTicket.reporter_id == current_user.id)
    if status_filter and status_filter.lower() != "all":
        sf = status_filter.lower()
        try:
            enum_v = models.MaintenanceTicketStatus(sf)
            q = q.filter(models.MaintenanceTicket.status == enum_v)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status_filter")
    rows = q.order_by(models.MaintenanceTicket.created_at.desc()).limit(200).all()
    return [_ticket_to_response(db, t) for t in rows]


@router.get("/tickets/{ticket_id}", response_model=MaintenanceTicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    t = (
        db.query(models.MaintenanceTicket)
        .options(
            joinedload(models.MaintenanceTicket.reporter),
            joinedload(models.MaintenanceTicket.hostel_room),
            joinedload(models.MaintenanceTicket.other_area),
        )
        .filter(models.MaintenanceTicket.id == ticket_id)
        .first()
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if current_user.role not in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER):
        if t.reporter_id != current_user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return _ticket_to_response(db, t)


@router.post("/tickets", response_model=MaintenanceTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    title: str = Form(...),
    description: str | None = Form(None),
    hostel_room_id: str | None = Form(None),
    other_area_id: str | None = Form(None),
    files: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    hr_raw = (hostel_room_id or "").strip()
    oa_raw = (other_area_id or "").strip()
    hr_id = int(hr_raw) if hr_raw else None
    oa_id = int(oa_raw) if oa_raw else None
    if bool(hr_id) == bool(oa_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of hostel_room_id or other_area_id",
        )
    if hr_id:
        if not db.query(models.HostelRoom).filter(models.HostelRoom.id == hr_id).first():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hostel room not found")
    if oa_id:
        if not db.query(models.OtherArea).filter(models.OtherArea.id == oa_id).first():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Facility / area not found")

    _ensure_upload_dir()
    ticket = models.MaintenanceTicket(
        reporter_id=current_user.id,
        title=title.strip()[:200],
        description=(description or "").strip()[:4000] or None,
        hostel_room_id=hr_id,
        other_area_id=oa_id,
        status=models.MaintenanceTicketStatus.OPEN,
        photo_paths=[],
    )
    db.add(ticket)
    db.flush()

    paths: list[str] = []
    file_list = list(files) if files else []
    if len(file_list) > MAX_FILES:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"At most {MAX_FILES} photos allowed")
    for f in file_list:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()[:12] or ".bin"
        if ext not in ALLOWED_EXT:
            ext = ".bin"
        dest_name = f"{ticket.id}_{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / dest_name
        size = 0
        with dest.open("wb") as buffer:
            while True:
                chunk = await f.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    db.rollback()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail=f"File too large (max {MAX_FILE_BYTES // (1024*1024)} MB per file)",
                    )
                buffer.write(chunk)
        paths.append(f"/uploads/maintenance/{dest_name}")

    ticket.photo_paths = paths
    db.commit()
    db.refresh(ticket)
    t2 = (
        db.query(models.MaintenanceTicket)
        .options(
            joinedload(models.MaintenanceTicket.reporter),
            joinedload(models.MaintenanceTicket.hostel_room),
            joinedload(models.MaintenanceTicket.other_area),
        )
        .filter(models.MaintenanceTicket.id == ticket.id)
        .first()
    )
    return _ticket_to_response(db, t2)


@router.patch("/tickets/{ticket_id}/status", response_model=MaintenanceTicketResponse)
def update_ticket_status(
    ticket_id: int,
    body: MaintenanceTicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    t = (
        db.query(models.MaintenanceTicket)
        .options(
            joinedload(models.MaintenanceTicket.reporter),
            joinedload(models.MaintenanceTicket.hostel_room),
            joinedload(models.MaintenanceTicket.other_area),
        )
        .filter(models.MaintenanceTicket.id == ticket_id)
        .first()
    )
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    try:
        t.status = models.MaintenanceTicketStatus(body.status)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    db.commit()
    db.refresh(t)
    return _ticket_to_response(db, t)
