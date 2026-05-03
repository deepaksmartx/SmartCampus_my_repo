from __future__ import annotations
"""
Campus, Building, Floor, FacilityType, OtherArea, HostelRoom APIs.
- Create & Delete: Admin only
- Update: Admin or Facility Manager
- Read & List: All authenticated users
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from . import models
from . import schemas
from .database import get_db
from .auth import verify_token, require_admin, require_admin_or_facility_manager

router = APIRouter(prefix="/campus", tags=["campus"])


def _blocking_booking_statuses():
    return (models.BookingStatus.PENDING, models.BookingStatus.ACCEPTED)


def _live_booking_counts_by_room(db: Session, room_ids: list[int]) -> dict[int, int]:
    if not room_ids:
        return {}
    now = datetime.now(timezone.utc)
    rows = (
        db.query(models.Booking.hostel_room_id, func.count(func.distinct(models.Booking.user_id)))
        .filter(
            models.Booking.hostel_room_id.in_(room_ids),
            models.Booking.status.in_(_blocking_booking_statuses()),
            models.Booking.start_time < now,
            models.Booking.end_time > now,
        )
        .group_by(models.Booking.hostel_room_id)
        .all()
    )
    return {int(r[0]): int(r[1]) for r in rows if r[0] is not None}


def _booking_user_brief(u: models.User) -> schemas.BookingUserBrief:
    r = u.role
    return schemas.BookingUserBrief(
        id=u.id,
        name=u.name,
        email=u.email,
        phone_number=u.phone_number,
        role=r.value if hasattr(r, "value") else str(r),
    )


# ---------- Campus ----------
@router.get("/campuses", response_model=list[schemas.CampusResponse])
def list_campuses(db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    return db.query(models.Campus).all()

@router.get("/campuses/{campus_id}", response_model=schemas.CampusResponse)
def get_campus(campus_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    obj = db.query(models.Campus).filter(models.Campus.id == campus_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Campus not found")
    return obj

@router.post("/campuses", response_model=schemas.CampusResponse)
def create_campus(p: schemas.CampusCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = models.Campus(name=p.name, location=p.location)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.patch("/campuses/{campus_id}", response_model=schemas.CampusResponse)
def update_campus(campus_id: int, p: schemas.CampusUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin_or_facility_manager)):
    obj = db.query(models.Campus).filter(models.Campus.id == campus_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Campus not found")
    if p.name is not None:
        obj.name = p.name
    if p.location is not None:
        obj.location = p.location
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/campuses/{campus_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campus(campus_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = db.query(models.Campus).filter(models.Campus.id == campus_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Campus not found")
    db.delete(obj)
    db.commit()
    return None

# ---------- Building ----------
@router.get("/buildings", response_model=list[schemas.BuildingResponse])
def list_buildings(db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    return db.query(models.Building).all()

@router.get("/buildings/{building_id}", response_model=schemas.BuildingResponse)
def get_building(building_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    obj = db.query(models.Building).filter(models.Building.id == building_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Building not found")
    return obj

@router.post("/buildings", response_model=schemas.BuildingResponse)
def create_building(p: schemas.BuildingCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = models.Building(name=p.name, campus_id=p.campus_id)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.patch("/buildings/{building_id}", response_model=schemas.BuildingResponse)
def update_building(building_id: int, p: schemas.BuildingUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin_or_facility_manager)):
    obj = db.query(models.Building).filter(models.Building.id == building_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Building not found")
    if p.name is not None:
        obj.name = p.name
    if p.campus_id is not None:
        obj.campus_id = p.campus_id
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/buildings/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_building(building_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = db.query(models.Building).filter(models.Building.id == building_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Building not found")
    db.delete(obj)
    db.commit()
    return None

# ---------- Floor ----------
@router.get("/floors", response_model=list[schemas.FloorResponse])
def list_floors(db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    return db.query(models.Floor).all()

@router.get("/floors/{floor_id}", response_model=schemas.FloorResponse)
def get_floor(floor_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    obj = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Floor not found")
    return obj

@router.post("/floors", response_model=schemas.FloorResponse)
def create_floor(p: schemas.FloorCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = models.Floor(building_id=p.building_id, floor_no=p.floor_no)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.patch("/floors/{floor_id}", response_model=schemas.FloorResponse)
def update_floor(floor_id: int, p: schemas.FloorUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin_or_facility_manager)):
    obj = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Floor not found")
    if p.building_id is not None:
        obj.building_id = p.building_id
    if p.floor_no is not None:
        obj.floor_no = p.floor_no
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/floors/{floor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_floor(floor_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = db.query(models.Floor).filter(models.Floor.id == floor_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Floor not found")
    db.delete(obj)
    db.commit()
    return None

# ---------- FacilityType ----------
@router.get("/facility-types", response_model=list[schemas.FacilityTypeResponse])
def list_facility_types(db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    return db.query(models.FacilityType).all()

@router.get("/facility-types/{ft_id}", response_model=schemas.FacilityTypeResponse)
def get_facility_type(ft_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    obj = db.query(models.FacilityType).filter(models.FacilityType.id == ft_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Facility type not found")
    return obj


@router.post("/facility-types", response_model=schemas.FacilityTypeResponse)
def create_facility_type(p: schemas.FacilityTypeCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = models.FacilityType(name=models.FacilityTypeName(p.name.value))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/facility-types/{ft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility_type(ft_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = db.query(models.FacilityType).filter(models.FacilityType.id == ft_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Facility type not found")
    db.delete(obj)
    db.commit()
    return None

# ---------- OtherArea ----------
@router.get("/other-areas", response_model=list[schemas.OtherAreaResponse])
def list_other_areas(db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    return db.query(models.OtherArea).all()

@router.get("/other-areas/{area_id}", response_model=schemas.OtherAreaResponse)
def get_other_area(area_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    obj = db.query(models.OtherArea).filter(models.OtherArea.id == area_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Other area not found")
    return obj

@router.post("/other-areas", response_model=schemas.OtherAreaResponse)
def create_other_area(p: schemas.OtherAreaCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    ft = db.query(models.FacilityType).filter(models.FacilityType.id == p.facility_type_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Facility type not found")
    obj = models.OtherArea(
        name=p.name, building_id=p.building_id, floor_id=p.floor_id,
        capacity=p.capacity, facility_type_id=p.facility_type_id,
        active=p.active,
        eligibility_rules=p.eligibility_rules,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.patch("/other-areas/{area_id}", response_model=schemas.OtherAreaResponse)
def update_other_area(area_id: int, p: schemas.OtherAreaUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin_or_facility_manager)):
    obj = db.query(models.OtherArea).filter(models.OtherArea.id == area_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Other area not found")
    for k, v in p.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/other-areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_other_area(area_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = db.query(models.OtherArea).filter(models.OtherArea.id == area_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Other area not found")
    db.delete(obj)
    db.commit()
    return None

# ---------- HostelRoom ----------
@router.get("/hostel-rooms", response_model=list[schemas.HostelRoomWithLiveCount])
def list_hostel_rooms(
    building_id: int | None = Query(None, description="Filter by building"),
    floor_id: int | None = Query(None, description="Filter by floor"),
    facility_type_id: int | None = Query(None, description="Filter by facility type (e.g. men's/ladies' hostel)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    q = db.query(models.HostelRoom)
    if building_id is not None:
        q = q.filter(models.HostelRoom.building_id == building_id)
    if floor_id is not None:
        q = q.filter(models.HostelRoom.floor_id == floor_id)
    if facility_type_id is not None:
        q = q.filter(models.HostelRoom.facility_type_id == facility_type_id)
    rows = q.all()
    counts = _live_booking_counts_by_room(db, [r.id for r in rows])
    out: list[schemas.HostelRoomWithLiveCount] = []
    for r in rows:
        base = schemas.HostelRoomResponse.model_validate(r)
        out.append(
            schemas.HostelRoomWithLiveCount(
                **base.model_dump(),
                live_booking_count=counts.get(r.id, 0),
            )
        )
    return out


@router.get(
    "/hostel-rooms/{room_id}/live-occupancy",
    response_model=schemas.HostelRoomLiveOccupancyResponse,
)
def get_hostel_room_live_occupancy(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    room = db.query(models.HostelRoom).filter(models.HostelRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Hostel room not found")
    reg_ids = room.inmate_profiles if isinstance(room.inmate_profiles, list) else []
    uid_list: list[int] = []
    for x in reg_ids:
        try:
            uid_list.append(int(x))
        except (TypeError, ValueError):
            continue
    registered_users = (
        db.query(models.User).filter(models.User.id.in_(uid_list)).all() if uid_list else []
    )
    now = datetime.now(timezone.utc)
    bookings = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.user))
        .filter(
            models.Booking.hostel_room_id == room_id,
            models.Booking.status.in_(_blocking_booking_statuses()),
            models.Booking.start_time < now,
            models.Booking.end_time > now,
        )
        .all()
    )
    seen: dict[int, models.User] = {}
    for b in bookings:
        if b.user:
            seen[b.user.id] = b.user
    return schemas.HostelRoomLiveOccupancyResponse(
        room_id=room.id,
        registered_inmates=[_booking_user_brief(u) for u in registered_users],
        active_bookers=[_booking_user_brief(u) for u in seen.values()],
    )


@router.get("/hostel-rooms/{room_id}", response_model=schemas.HostelRoomResponse)
def get_hostel_room(room_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    obj = db.query(models.HostelRoom).filter(models.HostelRoom.id == room_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Hostel room not found")
    return obj

@router.post("/hostel-rooms", response_model=schemas.HostelRoomResponse)
def create_hostel_room(p: schemas.HostelRoomCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    ft = db.query(models.FacilityType).filter(models.FacilityType.id == p.facility_type_id).first()
    if not ft:
        raise HTTPException(status_code=404, detail="Facility type not found")
    inmate = p.inmate_profiles or []
    obj = models.HostelRoom(
        roomno=p.roomno, room_type=models.RoomType(p.room_type.value), facility_type_id=p.facility_type_id,
        building_id=p.building_id, floor_id=p.floor_id,
        inmate_profiles=inmate, room_capacity=p.room_capacity,
        eligibility_rules=p.eligibility_rules,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.patch("/hostel-rooms/{room_id}", response_model=schemas.HostelRoomResponse)
def update_hostel_room(room_id: int, p: schemas.HostelRoomUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin_or_facility_manager)):
    obj = db.query(models.HostelRoom).filter(models.HostelRoom.id == room_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Hostel room not found")
    data = p.model_dump(exclude_unset=True)
    if "room_type" in data and data["room_type"] is not None:
        rt = data["room_type"]
        data["room_type"] = models.RoomType(rt.value if hasattr(rt, "value") else rt)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/hostel-rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hostel_room(room_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)):
    obj = db.query(models.HostelRoom).filter(models.HostelRoom.id == room_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Hostel room not found")
    db.delete(obj)
    db.commit()
    return None
