from __future__ import annotations
"""Hostel room allocations to students (Admin)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .auth import verify_token, require_admin, require_admin_or_facility_manager
from .schemas_iot import RoomAllocationCreate, RoomAllocationResponse, RoomInviteResponse
from .services.booking_eligibility import assert_user_eligible_for_booking
from .services.notification_service import create_notification
from typing import Dict

router = APIRouter(prefix="/room-allocations", tags=["room-allocations"])


@router.get("", response_model=list[RoomAllocationResponse])
def list_allocations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    if current_user.role not in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin or Facility Manager only")
    return db.query(models.RoomAllocation).order_by(models.RoomAllocation.allocation_date.desc()).all()


@router.post("", response_model=RoomAllocationResponse)
def create_allocation(
    body: RoomAllocationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    room = db.query(models.HostelRoom).filter(models.HostelRoom.id == body.room_id).first()
    if not room:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Room not found")
    student = db.query(models.User).filter(models.User.id == body.student_id).first()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student user not found")
    if student.role not in (models.UserRole.STUDENT, models.UserRole.STAFF):
        pass
    obj = models.RoomAllocation(
        room_id=body.room_id,
        student_id=body.student_id,
        allocation_date=body.allocation_date,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    obj = db.query(models.RoomAllocation).filter(models.RoomAllocation.id == allocation_id).first()
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(obj)
    db.commit()
    return None

@router.post("/invite-unhoused", response_model=RoomInviteResponse)
def invite_unhoused_students(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    # 1. Find all active students
    students = db.query(models.User).filter(
        models.User.role == models.UserRole.STUDENT,
        models.User.is_active == True
    ).all()
    
    # 2. Get students who have a pending/accepted booking for a hostel room
    # or are already in an inmate_profiles list of a hostel room
    booked_user_ids = set()
    blocking_statuses = (models.BookingStatus.PENDING, models.BookingStatus.ACCEPTED)
    active_bookings = db.query(models.Booking).filter(
        models.Booking.status.in_(blocking_statuses),
        models.Booking.hostel_room_id.isnot(None)
    ).all()
    for b in active_bookings:
        booked_user_ids.add(b.user_id)
        
    all_rooms = db.query(models.HostelRoom).filter(
        models.HostelRoom.staff_only == False
    ).all()
    
    for r in all_rooms:
        if isinstance(r.inmate_profiles, list):
            for uid in r.inmate_profiles:
                try:
                    booked_user_ids.add(int(uid))
                except ValueError:
                    pass
                    
    unhoused_students = [s for s in students if s.id not in booked_user_ids]
    
    # 3. Match unhoused students to available rooms
    invites_sent = 0
    room_alloc_counts = {} # track tentative allocations to prevent overbooking
    
    for r in all_rooms:
        inmate_count = len(r.inmate_profiles) if isinstance(r.inmate_profiles, list) else 0
        b_count = sum(1 for b in active_bookings if b.hostel_room_id == r.id)
        room_alloc_counts[r.id] = inmate_count + b_count
        
    for student in unhoused_students:
        for room in all_rooms:
            # Check capacity
            current_occupancy = room_alloc_counts.get(room.id, 0)
            if current_occupancy >= room.room_capacity:
                continue
                
            # Check eligibility
            rules = room.eligibility_rules if isinstance(room.eligibility_rules, dict) else None
            try:
                assert_user_eligible_for_booking(student, rules, facility_label=f"hostel room {room.roomno}")
                # Eligible! Send email invite and increment count
                room_alloc_counts[room.id] = current_occupancy + 1
                
                uri = f"http://localhost:3000/dashboard?autoBookRoomId={room.id}"
                body = (
                    f"Dear {student.name},\n\n"
                    f"You have been successfully matched with an available hostel room: Room {room.roomno}.\n\n"
                    f"Please click the link below to review the room details and immediately confirm your booking:\n"
                    f"{uri}\n\n"
                    f"Best regards,\n"
                    f"SmartCampus Administration"
                )
                create_notification(
                    db,
                    user_id=student.id,
                    title="Action Required: Reserve Your Allocated Hostel Room",
                    body=body,
                    category=models.NotificationCategory.SYSTEM.value,
                    send_email=True
                )
                invites_sent += 1
                break # Only map to code one bed/room per student
            except HTTPException:
                continue # not eligible for this room, try next

    db.commit()
    return {"invites_sent": invites_sent}
