from __future__ import annotations
"""
Booking API. Hostel rooms share capacity (pending/accepted overlap); other areas are exclusive.
Dining: meal_slot + menu item ids. Optional per-facility inventory selections.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import models
from . import schemas
from .database import get_db
from .auth import (
    verify_token,
    require_student_or_staff,
    require_admin_or_facility_manager,
)
from .services.notification_service import (
    notify_booking_created,
    notify_booking_reviewed,
    notify_booking_displaced_by_vip,
)
from .services.booking_eligibility import assert_user_eligible_for_booking

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bookings", tags=["bookings"])

MEAL_SLOTS = frozenset({"breakfast", "lunch", "dinner", "snack"})

MIN_HOSTEL_BOOKING_DURATION = timedelta(days=1)
MIN_OTHER_AREA_BOOKING_DURATION = timedelta(hours=2)


def _assert_min_booking_duration(
    hostel_room_id: int | None,
    other_area_id: int | None,
    start_t: datetime,
    end_t: datetime,
) -> None:
    delta = end_t - start_t
    if hostel_room_id is not None:
        if delta < MIN_HOSTEL_BOOKING_DURATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hostel bookings must be at least 1 day from start to end",
            )
    elif other_area_id is not None:
        if delta < MIN_OTHER_AREA_BOOKING_DURATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bookings for this facility must be at least 2 hours from start to end",
            )


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _blocking_statuses():
    return (models.BookingStatus.PENDING, models.BookingStatus.ACCEPTED)


def _overlap_clause(start1, end1, start2, end2):
    return and_(start1 < end2, end1 > start2)


def find_booking_conflict_exclusive(
    db: Session,
    hostel_room_id: int | None,
    other_area_id: int | None,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
    *,
    vip_overlap_only: bool = False,
):
    """Overlapping pending/accepted booking for the same facility.
    If vip_overlap_only, only counts VIP bookings (for new VIP placement after non-VIP cleared)."""
    start_time = _as_utc_aware(start_time)
    end_time = _as_utc_aware(end_time)
    q = db.query(models.Booking).filter(
        models.Booking.status.in_(_blocking_statuses()),
        _overlap_clause(models.Booking.start_time, models.Booking.end_time, start_time, end_time),
    )
    if hostel_room_id is not None:
        q = q.filter(models.Booking.hostel_room_id == hostel_room_id)
    else:
        q = q.filter(models.Booking.other_area_id == other_area_id)
    if exclude_booking_id is not None:
        q = q.filter(models.Booking.id != exclude_booking_id)
    if vip_overlap_only:
        q = q.filter(models.Booking.priority == models.BookingPriority.VIP)
    return q.first()


def count_hostel_overlapping_bookings(
    db: Session,
    room_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
) -> int:
    start_time = _as_utc_aware(start_time)
    end_time = _as_utc_aware(end_time)
    q = db.query(func.count(models.Booking.id)).filter(
        models.Booking.hostel_room_id == room_id,
        models.Booking.status.in_(_blocking_statuses()),
        _overlap_clause(models.Booking.start_time, models.Booking.end_time, start_time, end_time),
    )
    if exclude_booking_id is not None:
        q = q.filter(models.Booking.id != exclude_booking_id)
    return int(q.scalar() or 0)


def user_hostel_room_overlap_exists(
    db: Session,
    user_id: int,
    room_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
) -> bool:
    start_time = _as_utc_aware(start_time)
    end_time = _as_utc_aware(end_time)
    q = db.query(models.Booking).filter(
        models.Booking.user_id == user_id,
        models.Booking.hostel_room_id == room_id,
        models.Booking.status.in_(_blocking_statuses()),
        _overlap_clause(models.Booking.start_time, models.Booking.end_time, start_time, end_time),
    )
    if exclude_booking_id is not None:
        q = q.filter(models.Booking.id != exclude_booking_id)
    return q.first() is not None


def assert_hostel_booking_allowed(
    db: Session,
    user_id: int,
    room_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
):
    room = db.query(models.HostelRoom).filter(models.HostelRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Hostel room not found")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if getattr(room, "staff_only", False) and getattr(user, "role", "") == models.UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="This facility is reserved for staff only")
    if user_hostel_room_overlap_exists(db, user_id, room_id, start_time, end_time, exclude_booking_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an overlapping booking for this room",
        )
    n = count_hostel_overlapping_bookings(db, room_id, start_time, end_time, exclude_booking_id)
    if n >= room.room_capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No beds available in this room for the selected period",
        )


def assert_other_area_booking_allowed(
    db: Session,
    other_area_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
    *,
    new_booking_is_vip: bool = False,
    user_id: int | None = None,
):
    """Non-VIP: cannot overlap any booking. VIP: only cannot overlap another VIP."""
    area = db.query(models.OtherArea).filter(models.OtherArea.id == other_area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Facility not found")
    if user_id:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if getattr(area, "staff_only", False) and getattr(user, "role", "") == models.UserRole.STUDENT:
            raise HTTPException(status_code=403, detail="This facility is reserved for staff only")
    conflict = find_booking_conflict_exclusive(
        db,
        None,
        other_area_id,
        start_time,
        end_time,
        exclude_booking_id,
        vip_overlap_only=new_booking_is_vip,
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This time slot overlaps another VIP booking for this facility"
                if new_booking_is_vip
                else "This time slot overlaps an existing booking for this facility"
            ),
        )


def _reject_overlapping_non_vip_other_area_bookings(
    db: Session,
    other_area_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None,
) -> int:
    """Mark overlapping normal-priority area bookings as rejected; notify users. Returns count updated."""
    start_time = _as_utc_aware(start_time)
    end_time = _as_utc_aware(end_time)
    area = db.query(models.OtherArea).filter(models.OtherArea.id == other_area_id).first()
    facility_name = area.name if area else f"Area #{other_area_id}"
    q = db.query(models.Booking).filter(
        models.Booking.other_area_id == other_area_id,
        models.Booking.status.in_(_blocking_statuses()),
        models.Booking.priority == models.BookingPriority.NORMAL,
        _overlap_clause(models.Booking.start_time, models.Booking.end_time, start_time, end_time),
    )
    if exclude_booking_id is not None:
        q = q.filter(models.Booking.id != exclude_booking_id)
    victims = list(q.all())
    for b in victims:
        bid = b.id
        uid = b.user_id
        notify_booking_displaced_by_vip(
            db,
            displaced_user_id=uid,
            rejected_booking_id=bid,
            facility_name=facility_name,
            start_time=b.start_time,
            end_time=b.end_time,
        )
        b.status = models.BookingStatus.REJECTED
    if victims:
        db.flush()
    return len(victims)


def _facility_scope_for_booking(hostel_room_id: int | None, other_area_id: int | None) -> tuple[str, int]:
    if hostel_room_id is not None:
        return "hostel_room", hostel_room_id
    return "other_area", other_area_id  # type: ignore


def sum_inventory_allocated(
    db: Session,
    inventory_item_id: int,
    scope: str,
    facility_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
) -> int:
    start_time = _as_utc_aware(start_time)
    end_time = _as_utc_aware(end_time)
    q = db.query(models.Booking).filter(
        models.Booking.status.in_(_blocking_statuses()),
        _overlap_clause(models.Booking.start_time, models.Booking.end_time, start_time, end_time),
    )
    if scope == "hostel_room":
        q = q.filter(models.Booking.hostel_room_id == facility_id)
    else:
        q = q.filter(models.Booking.other_area_id == facility_id)
    if exclude_booking_id is not None:
        q = q.filter(models.Booking.id != exclude_booking_id)
    total = 0
    for b in q.all():
        for sel in b.inventory_selections or []:
            try:
                iid = int(sel.get("inventory_item_id", 0))
                qty = int(sel.get("quantity", 0))
            except (TypeError, ValueError):
                continue
            if iid == inventory_item_id and qty > 0:
                total += qty
    return total


def validate_and_normalize_inventory_selections(
    db: Session,
    selections: list[schemas.InventorySelectionLine] | None,
    hostel_room_id: int | None,
    other_area_id: int | None,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
) -> list[dict]:
    if not selections:
        return []
    scope, fid = _facility_scope_for_booking(hostel_room_id, other_area_id)
    out: list[dict] = []
    seen_ids: set[int] = set()
    for line in selections:
        if line.inventory_item_id in seen_ids:
            raise HTTPException(status_code=400, detail="Duplicate inventory_item_id in selections")
        seen_ids.add(line.inventory_item_id)
        item = (
            db.query(models.FacilityInventoryItem)
            .filter(models.FacilityInventoryItem.id == line.inventory_item_id)
            .first()
        )
        if not item:
            raise HTTPException(status_code=400, detail=f"Unknown inventory item {line.inventory_item_id}")
        if item.facility_scope != scope or item.facility_id != fid:
            raise HTTPException(
                status_code=400,
                detail=f"Inventory item {line.inventory_item_id} does not belong to this facility",
            )
        allocated = sum_inventory_allocated(
            db, item.id, scope, fid, start_time, end_time, exclude_booking_id
        )
        if allocated + line.quantity > item.quantity_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Not enough stock for '{item.name}' ({allocated} already allocated in this period)",
            )
        out.append({"inventory_item_id": item.id, "quantity": line.quantity})
    return out


def _user_brief(u: models.User) -> schemas.BookingUserBrief:
    r = u.role
    return schemas.BookingUserBrief(
        id=u.id,
        name=u.name,
        email=u.email,
        phone_number=u.phone_number,
        role=r.value if hasattr(r, "value") else str(r),
    )


def _booking_to_response(b: models.Booking, include_user: bool = False) -> schemas.BookingResponse:
    uinfo = None
    if include_user and b.user is not None:
        uinfo = _user_brief(b.user)
    st = b.status
    status_str = st.value if hasattr(st, "value") else str(st)
    pr = getattr(b, "priority", None)
    priority_str = pr.value if hasattr(pr, "value") else str(pr or "normal")
    created_at = getattr(b, "created_at", None)
    menu_ids = b.dining_menu_item_ids if isinstance(b.dining_menu_item_ids, list) else []
    inv_sel = b.inventory_selections if isinstance(b.inventory_selections, list) else []
    mid_out: list[int] = []
    for x in menu_ids:
        try:
            mid_out.append(int(x))
        except (TypeError, ValueError):
            continue
    return schemas.BookingResponse(
        id=b.id,
        user_id=b.user_id,
        start_time=b.start_time,
        end_time=b.end_time,
        status=status_str,
        priority=priority_str,
        created_at=created_at,
        hostel_room_id=b.hostel_room_id,
        other_area_id=b.other_area_id,
        meal_preference=b.meal_preference,
        meal_slot=b.meal_slot,
        dining_menu_item_ids=mid_out,
        inventory_selections=inv_sel,
        user=uinfo,
    )


def _eligibility_rules_and_label(
    db: Session,
    hostel_room_id: int | None,
    other_area_id: int | None,
) -> tuple[dict | None, str]:
    if hostel_room_id is not None:
        room = db.query(models.HostelRoom).filter(models.HostelRoom.id == hostel_room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Hostel room not found")
        rules = getattr(room, "eligibility_rules", None)
        return (rules if isinstance(rules, dict) else None, f"hostel room {room.roomno}")
    if other_area_id is not None:
        area = db.query(models.OtherArea).filter(models.OtherArea.id == other_area_id).first()
        if not area:
            raise HTTPException(status_code=404, detail="Facility not found")
        rules = getattr(area, "eligibility_rules", None)
        return (rules if isinstance(rules, dict) else None, area.name)
    raise HTTPException(status_code=400, detail="Invalid booking target")


def _assert_booking_eligibility(
    db: Session,
    user: models.User,
    hostel_room_id: int | None,
    other_area_id: int | None,
) -> None:
    rules, label = _eligibility_rules_and_label(db, hostel_room_id, other_area_id)
    assert_user_eligible_for_booking(user, rules, facility_label=label)


def _load_other_area_dining(db: Session, other_area_id: int) -> tuple[models.OtherArea, bool]:
    area = (
        db.query(models.OtherArea)
        .options(joinedload(models.OtherArea.facility_type))
        .filter(models.OtherArea.id == other_area_id)
        .first()
    )
    if not area:
        raise HTTPException(status_code=404, detail="Facility not found")
    ft_name = area.facility_type.name
    ft_val = ft_name.value if hasattr(ft_name, "value") else str(ft_name)
    is_dining = ft_val == models.FacilityTypeName.DINING.value
    return area, is_dining


def _validate_dining_booking(
    db: Session,
    body: schemas.BookingCreate,
    is_dining: bool,
) -> tuple[str | None, list[int], str | None]:
    """Returns (meal_slot, menu_ids, meal_preference)."""
    if not is_dining:
        if body.meal_slot is not None or (body.dining_menu_item_ids and len(body.dining_menu_item_ids) > 0):
            raise HTTPException(
                status_code=400,
                detail="meal_slot and dining menu apply only to mess/dining bookings",
            )
        if body.meal_preference is not None:
            raise HTTPException(
                status_code=400,
                detail="meal_preference applies only to mess/dining bookings",
            )
        return None, [], None

    if not body.meal_slot or body.meal_slot not in MEAL_SLOTS:
        raise HTTPException(
            status_code=400,
            detail="meal_slot is required for dining (breakfast, lunch, dinner, snack)",
        )
    if not body.dining_menu_item_ids or len(body.dining_menu_item_ids) < 1:
        raise HTTPException(
            status_code=400,
            detail="Select at least one menu item for dining",
        )
    oid = body.other_area_id
    items = (
        db.query(models.DiningMenuItem)
        .filter(
            models.DiningMenuItem.other_area_id == oid,
            models.DiningMenuItem.active.is_(True),
            models.DiningMenuItem.id.in_(body.dining_menu_item_ids),
        )
        .all()
    )
    by_id = {i.id: i for i in items}
    for mid in body.dining_menu_item_ids:
        m = by_id.get(mid)
        if not m:
            raise HTTPException(status_code=400, detail=f"Invalid or inactive menu item id {mid}")
        if (m.meal_slot or "").lower() != body.meal_slot:
            raise HTTPException(
                status_code=400,
                detail=f"Menu item {mid} is not available for meal_slot {body.meal_slot}",
            )
    meal_pref = body.meal_preference
    if meal_pref is not None and meal_pref not in ("veg", "non_veg"):
        raise HTTPException(status_code=400, detail="meal_preference must be veg or non_veg")
    for mid in body.dining_menu_item_ids:
        m = by_id.get(mid)
        d = (m.diet or "either").lower()
        if meal_pref == "veg" and d == "non_veg":
            raise HTTPException(
                status_code=400,
                detail="A selected menu item is not compatible with veg preference",
            )
        if meal_pref == "non_veg" and d == "veg":
            raise HTTPException(
                status_code=400,
                detail="A selected menu item is not compatible with non-veg preference",
            )
    return body.meal_slot, list(dict.fromkeys(body.dining_menu_item_ids)), meal_pref


def _apply_booking_conflict_rules(
    db: Session,
    user_id: int,
    hostel_room_id: int | None,
    other_area_id: int | None,
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
    *,
    other_area_new_booking_is_vip: bool = False,
):
    if hostel_room_id is not None:
        assert_hostel_booking_allowed(db, user_id, hostel_room_id, start_time, end_time, exclude_booking_id)
    else:
        assert_other_area_booking_allowed(
            db,
            other_area_id,
            start_time,
            end_time,
            exclude_booking_id,
            new_booking_is_vip=other_area_new_booking_is_vip,
            user_id=user_id,
        )


@router.get("/preview/hostel-room", response_model=schemas.HostelRoomBookingPreview)
def hostel_room_booking_preview(
    room_id: int = Query(..., ge=1),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    start_t = _as_utc_aware(start_time)
    end_t = _as_utc_aware(end_time)
    if end_t <= start_t:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    _assert_min_booking_duration(room_id, None, start_t, end_t)
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
    registered_users = db.query(models.User).filter(models.User.id.in_(uid_list)).all() if uid_list else []
    registered_inmates = [_user_brief(u) for u in registered_users]

    ov = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.user))
        .filter(
            models.Booking.hostel_room_id == room_id,
            models.Booking.status.in_(_blocking_statuses()),
            _overlap_clause(models.Booking.start_time, models.Booking.end_time, start_t, end_t),
        )
        .all()
    )
    seen: dict[int, models.User] = {}
    for b in ov:
        if b.user:
            seen[b.user.id] = b.user
    booking_occupants = [_user_brief(u) for u in seen.values()]
    n = len(ov)
    cap = room.room_capacity
    remaining = max(0, cap - n)
    return schemas.HostelRoomBookingPreview(
        room_id=room.id,
        room_capacity=cap,
        overlapping_booking_count=n,
        slots_remaining=remaining,
        registered_inmates=registered_inmates,
        booking_occupants=booking_occupants,
    )


@router.post("", response_model=schemas.BookingResponse)
def create_booking(
    body: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_student_or_staff),
):
    if bool(body.hostel_room_id) == bool(body.other_area_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of hostel_room_id or other_area_id",
        )
    start_t = _as_utc_aware(body.start_time)
    end_t = _as_utc_aware(body.end_time)
    if end_t <= start_t:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be after start_time",
        )
    _assert_min_booking_duration(body.hostel_room_id, body.other_area_id, start_t, end_t)

    meal_slot: str | None = None
    menu_ids: list[int] = []
    meal_pref: str | None = None
    if body.hostel_room_id is not None:
        if body.request_vip:
            raise HTTPException(
                status_code=400,
                detail="VIP booking applies only to non-hostel facilities (halls, courts, dining, etc.)",
            )
        if body.meal_preference is not None or body.meal_slot or (body.dining_menu_item_ids or []):
            raise HTTPException(
                status_code=400,
                detail="meal and menu fields apply only to mess/dining (other_area) bookings",
            )
    else:
        _, is_dining = _load_other_area_dining(db, body.other_area_id)
        meal_slot, menu_ids, meal_pref = _validate_dining_booking(db, body, is_dining)

    _assert_booking_eligibility(db, current_user, body.hostel_room_id, body.other_area_id)

    if body.request_vip:
        r = current_user.role
        if r != models.UserRole.STAFF:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Staff can request a VIP booking",
            )

    # VIP overlaps allowed at create; overlapping non-VIP bookings are cancelled only when Admin/FM accepts the VIP.
    other_vip = bool(body.other_area_id and body.request_vip)

    inv_norm = validate_and_normalize_inventory_selections(
        db,
        body.inventory_selections,
        body.hostel_room_id,
        body.other_area_id,
        start_t,
        end_t,
        None,
    )

    _apply_booking_conflict_rules(
        db,
        current_user.id,
        body.hostel_room_id,
        body.other_area_id,
        start_t,
        end_t,
        None,
        other_area_new_booking_is_vip=other_vip,
    )

    booking = models.Booking(
        user_id=current_user.id,
        start_time=start_t,
        end_time=end_t,
        status=models.BookingStatus.PENDING,
        priority=models.BookingPriority.VIP if other_vip else models.BookingPriority.NORMAL,
        hostel_room_id=body.hostel_room_id,
        other_area_id=body.other_area_id,
        meal_preference=meal_pref,
        meal_slot=meal_slot,
        dining_menu_item_ids=menu_ids or None,
        inventory_selections=inv_norm or None,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    try:
        notify_booking_created(db, booking, current_user)
    except Exception as e:
        logger.warning("notify_booking_created failed: %s", e)
    return _booking_to_response(booking, False)


def _apply_booking_status_filter(q, sf: str):
    if sf == "all":
        return q
    if sf == "pending":
        return q.filter(models.Booking.status == models.BookingStatus.PENDING)
    if sf == "accepted":
        return q.filter(models.Booking.status == models.BookingStatus.ACCEPTED)
    if sf == "rejected":
        return q.filter(models.Booking.status == models.BookingStatus.REJECTED)
    raise HTTPException(status_code=400, detail="status_filter must be pending, accepted, rejected, or all")


@router.get("", response_model=list[schemas.BookingResponse])
def list_bookings(
    status_filter: Optional[str] = Query(
        None,
        description="Admin/FM: optional (default pending). Staff: pass this to see the review queue; omit for own bookings only.",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    q = db.query(models.Booking)
    role = current_user.role
    # Admin/FM: always full queue view. Staff: only when status_filter is sent (Review bookings UI).
    use_queue = role in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER) or (
        role == models.UserRole.STAFF and status_filter is not None
    )
    if use_queue:
        sf = (status_filter or "pending").lower()
        q = _apply_booking_status_filter(q, sf)
        q = q.order_by(
            desc(models.Booking.priority),
            models.Booking.created_at.asc(),
            models.Booking.id.asc(),
        )
        rows = q.options(joinedload(models.Booking.user)).all()
        return [_booking_to_response(b, True) for b in rows]
    rows = (
        q.filter(models.Booking.user_id == current_user.id)
        .order_by(models.Booking.start_time.desc())
        .all()
    )
    return [_booking_to_response(b, False) for b in rows]


@router.patch("/{booking_id}/priority", response_model=schemas.BookingResponse)
def update_booking_priority(
    booking_id: int,
    body: schemas.BookingPriorityUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    """Admin/FM: adjust queue priority on a pending booking (does not cancel others; VIP pre-emption runs on accept)."""
    booking = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.user))
        .filter(models.Booking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != models.BookingStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending bookings can change priority")
    if body.priority == "vip":
        if booking.hostel_room_id is not None:
            raise HTTPException(
                status_code=400,
                detail="VIP applies only to non-hostel facility bookings",
            )
        if booking.other_area_id is None:
            raise HTTPException(status_code=400, detail="Invalid booking target")
        if find_booking_conflict_exclusive(
            db,
            None,
            booking.other_area_id,
            booking.start_time,
            booking.end_time,
            exclude_booking_id=booking.id,
            vip_overlap_only=True,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another VIP booking overlaps this time slot",
            )
        booking.priority = models.BookingPriority.VIP
    else:
        if booking.other_area_id is not None:
            if find_booking_conflict_exclusive(
                db,
                None,
                booking.other_area_id,
                booking.start_time,
                booking.end_time,
                exclude_booking_id=booking.id,
                vip_overlap_only=False,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another booking overlaps this slot; cannot clear VIP",
                )
        booking.priority = models.BookingPriority.NORMAL
    db.commit()
    db.refresh(booking)
    return _booking_to_response(booking, True)


@router.patch("/{booking_id}/review", response_model=schemas.BookingResponse)
def review_booking(
    booking_id: int,
    body: schemas.BookingReviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != models.BookingStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending bookings can be accepted or rejected")
    new_status = (
        models.BookingStatus.ACCEPTED
        if body.status == "accepted"
        else models.BookingStatus.REJECTED
    )
    if new_status == models.BookingStatus.ACCEPTED:
        accept_vip_area = (
            booking.other_area_id is not None
            and booking.priority == models.BookingPriority.VIP
        )
        if accept_vip_area:
            _reject_overlapping_non_vip_other_area_bookings(
                db,
                booking.other_area_id,
                booking.start_time,
                booking.end_time,
                exclude_booking_id=booking.id,
            )
        booker = db.query(models.User).filter(models.User.id == booking.user_id).first()
        if booker:
            _assert_booking_eligibility(
                db,
                booker,
                booking.hostel_room_id,
                booking.other_area_id,
            )
        _apply_booking_conflict_rules(
            db,
            booking.user_id,
            booking.hostel_room_id,
            booking.other_area_id,
            booking.start_time,
            booking.end_time,
            exclude_booking_id=booking.id,
            other_area_new_booking_is_vip=accept_vip_area,
        )
        lines = [
            schemas.InventorySelectionLine(
                inventory_item_id=int(s["inventory_item_id"]),
                quantity=int(s["quantity"]),
            )
            for s in (booking.inventory_selections or [])
            if isinstance(s, dict) and "inventory_item_id" in s and "quantity" in s
        ]
        validate_and_normalize_inventory_selections(
            db,
            lines if lines else None,
            booking.hostel_room_id,
            booking.other_area_id,
            booking.start_time,
            booking.end_time,
            exclude_booking_id=booking.id,
        )
    booking.status = new_status
    db.commit()
    booking = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.user))
        .filter(models.Booking.id == booking_id)
        .first()
    )
    try:
        if booking:
            notify_booking_reviewed(db, booking)
    except Exception as e:
        logger.warning("notify_booking_reviewed failed: %s", e)
    return _booking_to_response(booking, True)


@router.patch("/{booking_id}/times", response_model=schemas.BookingResponse)
def update_booking_times(
    booking_id: int,
    body: schemas.BookingTimesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_student_or_staff),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to modify this booking")
    if booking.status == models.BookingStatus.REJECTED:
        raise HTTPException(status_code=400, detail="Cannot modify a rejected booking; cancel or create a new booking")
    start_t = _as_utc_aware(body.start_time)
    end_t = _as_utc_aware(body.end_time)
    if end_t <= start_t:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    _assert_min_booking_duration(booking.hostel_room_id, booking.other_area_id, start_t, end_t)

    lines = [
        schemas.InventorySelectionLine(
            inventory_item_id=int(s["inventory_item_id"]),
            quantity=int(s["quantity"]),
        )
        for s in (booking.inventory_selections or [])
        if isinstance(s, dict) and "inventory_item_id" in s and "quantity" in s
    ]
    other_vip_reschedule = (
        booking.other_area_id is not None
        and booking.priority == models.BookingPriority.VIP
    )
    validate_and_normalize_inventory_selections(
        db,
        lines if lines else None,
        booking.hostel_room_id,
        booking.other_area_id,
        start_t,
        end_t,
        exclude_booking_id=booking.id,
    )
    booker = db.query(models.User).filter(models.User.id == booking.user_id).first()
    if booker:
        _assert_booking_eligibility(db, booker, booking.hostel_room_id, booking.other_area_id)
    _apply_booking_conflict_rules(
        db,
        booking.user_id,
        booking.hostel_room_id,
        booking.other_area_id,
        start_t,
        end_t,
        exclude_booking_id=booking.id,
        other_area_new_booking_is_vip=other_vip_reschedule,
    )

    booking.start_time = start_t
    booking.end_time = end_t
    if booking.status == models.BookingStatus.ACCEPTED:
        booking.status = models.BookingStatus.PENDING
    db.commit()
    db.refresh(booking)
    return _booking_to_response(booking, False)


@router.get("/{booking_id}", response_model=schemas.BookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    booking = (
        db.query(models.Booking)
        .options(joinedload(models.Booking.user))
        .filter(models.Booking.id == booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id and current_user.role not in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER):
        raise HTTPException(status_code=403, detail="Not allowed to view this booking")
    is_admin_fm = current_user.role in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER)
    return _booking_to_response(booking, is_admin_fm)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id and current_user.role not in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER):
        raise HTTPException(status_code=403, detail="Not allowed to cancel this booking")
    db.delete(booking)
    db.commit()
    return None
