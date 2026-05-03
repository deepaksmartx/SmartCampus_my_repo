from __future__ import annotations
from typing import Optional

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Enum, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from .database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    FACILITY_MANAGER = "Facility Manager"
    SECURITY = "Security"
    STUDENT = "Student"
    STAFF = "Staff"


def _coerce_user_role(value) -> UserRole:
    """Map DB string to UserRole: supports display values (Admin) and legacy PG labels (ADMIN, FACILITY_MANAGER)."""
    if isinstance(value, UserRole):
        return value
    s = str(value).strip() if value is not None else ""
    if not s:
        return UserRole.STUDENT
    # Legacy PostgreSQL enum labels = Python member names
    by_member_name = {
        "ADMIN": UserRole.ADMIN,
        "FACILITY_MANAGER": UserRole.FACILITY_MANAGER,
        "SECURITY": UserRole.SECURITY,
        "STUDENT": UserRole.STUDENT,
        "STAFF": UserRole.STAFF,
    }
    if s in by_member_name:
        return by_member_name[s]
    # Current canonical values: Admin, Facility Manager, …
    try:
        return UserRole(s)
    except ValueError:
        pass
    # Normalize "Facility Manager" -> FACILITY_MANAGER
    key = "_".join(s.split()).upper()
    if key in by_member_name:
        return by_member_name[key]
    try:
        return UserRole[key]
    except KeyError:
        return UserRole.STUDENT


def _resolve_role_enum(value) -> UserRole:
    """Normalize assignment / API input to models.UserRole (handles schemas.UserRole and str)."""
    if isinstance(value, UserRole):
        return value
    if isinstance(value, str):
        return _coerce_user_role(value)
    v = getattr(value, "value", None)
    if isinstance(v, str):
        return _coerce_user_role(v)
    s = str(value)
    if "UserRole." in s:
        part = s.replace("UserRole.", "").strip().split(".")[-1]
        try:
            return UserRole[part]
        except KeyError:
            pass
    return _coerce_user_role(s)


def _role_to_db_string(value, dialect) -> Optional[str]:
    """
    Bind role for SQL parameters.
    PostgreSQL native userrole enum uses labels ADMIN, FACILITY_MANAGER, … (Python member .name).
    SQLite / VARCHAR uses display strings Admin, Facility Manager, … (.value).
    """
    if value is None:
        return None
    ur = _resolve_role_enum(value)
    if dialect is not None and getattr(dialect, "name", None) == "postgresql":
        return ur.name
    return ur.value


class UserRoleColumn(TypeDecorator):
    """Maps UserRole to DB: PG enum labels (ADMIN) or string values (Admin) per dialect."""

    impl = String(50)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _role_to_db_string(value, dialect)

    def process_result_value(self, value, dialect):
        return _coerce_user_role(value)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone_number = Column(String(20), nullable=True)
    role = Column(UserRoleColumn(), nullable=False, default=UserRole.STUDENT)
    is_active = Column(Boolean, default=True, nullable=False)
    profile_photo = Column(String(500), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    # Allocation / eligibility (optional; used when facility has eligibility_rules)
    year_of_study = Column(Integer, nullable=True)
    department = Column(String(120), nullable=True)
    membership_tier = Column(String(20), nullable=True)  # basic | standard | premium
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<User id={self.id} name={self.name} email={self.email} role={self.role}>"


# --- Campus / Building / Floor / Facilities ---

class Campus(Base):
    __tablename__ = "campuses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    location = Column(String(500), nullable=True)
    buildings = relationship("Building", back_populates="campus")

class Building(Base):
    __tablename__ = "buildings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    campus_id = Column(Integer, ForeignKey("campuses.id"), nullable=False)
    campus = relationship("Campus", back_populates="buildings")
    floors = relationship("Floor", back_populates="building")

class Floor(Base):
    __tablename__ = "floors"
    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    floor_no = Column(Integer, nullable=False)
    building = relationship("Building", back_populates="floors")


class FacilityTypeName(str, enum.Enum):
    MENS_HOSTEL = "mens_hostel"
    LADIES_HOSTEL = "ladies_hostel"
    DINING = "dining"
    SPORTS = "sports"
    ACADEMIC_SPACES = "academic_spaces"

class FacilityType(Base):
    __tablename__ = "facility_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(Enum(FacilityTypeName), unique=True, nullable=False)


class RoomType(str, enum.Enum):
    SINGLE = "Single"
    DOUBLE = "Double"
    SUITE = "Suite"

class OtherArea(Base):
    __tablename__ = "other_areas"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=False)
    capacity = Column(Integer, nullable=True)
    facility_type_id = Column(Integer, ForeignKey("facility_types.id"), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    staff_only = Column(Boolean, default=False, nullable=False)
    eligibility_rules = Column(JSON, nullable=True)  # optional: min_year, max_year, allowed_departments, min_membership
    building = relationship("Building", backref="other_areas")
    floor = relationship("Floor", backref="other_areas")
    facility_type = relationship("FacilityType", backref="other_areas")

class HostelRoom(Base):
    __tablename__ = "hostel_rooms"
    id = Column(Integer, primary_key=True, index=True)
    roomno = Column(String(50), nullable=False)
    room_type = Column(Enum(RoomType), nullable=False)
    facility_type_id = Column(Integer, ForeignKey("facility_types.id"), nullable=False)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=True)
    inmate_profiles = Column(JSON, nullable=True, default=list)  # list of user ids (registered occupants)
    room_capacity = Column(Integer, nullable=False)  # max concurrent bookings (1 single, 2 double, etc.)
    staff_only = Column(Boolean, default=False, nullable=False)
    eligibility_rules = Column(JSON, nullable=True)
    facility_type = relationship("FacilityType", backref="hostel_rooms")
    building = relationship("Building", backref="hostel_rooms")
    floor = relationship("Floor", backref="hostel_rooms")


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class BookingPriority(str, enum.Enum):
    NORMAL = "normal"
    VIP = "vip"


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        Enum(BookingStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=BookingStatus.PENDING,
        nullable=False,
    )
    priority = Column(
        Enum(BookingPriority, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=BookingPriority.NORMAL,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    hostel_room_id = Column(Integer, ForeignKey("hostel_rooms.id"), nullable=True)
    other_area_id = Column(Integer, ForeignKey("other_areas.id"), nullable=True)
    meal_preference = Column(String(20), nullable=True)  # veg | non_veg for dining
    meal_slot = Column(String(20), nullable=True)  # breakfast | lunch | dinner | snack
    dining_menu_item_ids = Column(JSON, nullable=True, default=list)  # list of int ids
    inventory_selections = Column(JSON, nullable=True, default=list)  # [{"inventory_item_id":1,"quantity":2}]
    user = relationship("User", backref="bookings")
    hostel_room = relationship("HostelRoom", backref="bookings")
    other_area = relationship("OtherArea", backref="bookings")


# --- Dining menu (per mess / dining other_area) ---
class DiningMenuItem(Base):
    __tablename__ = "dining_menu_items"
    id = Column(Integer, primary_key=True, index=True)
    other_area_id = Column(Integer, ForeignKey("other_areas.id"), nullable=False, index=True)
    meal_slot = Column(String(20), nullable=False, index=True)  # breakfast | lunch | dinner | snack
    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    diet = Column(String(20), nullable=False, default="either")  # veg | non_veg | either
    active = Column(Boolean, default=True, nullable=False)
    other_area = relationship("OtherArea", backref="dining_menu_items")


# --- Facility stock: admin-defined items; students pick qty when booking ---
class FacilityInventoryItem(Base):
    __tablename__ = "facility_inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    facility_scope = Column(String(20), nullable=False, index=True)  # hostel_room | other_area
    facility_id = Column(Integer, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    quantity_available = Column(Integer, nullable=False)  # total units for allocation across overlapping bookings


# --- Room allocation (hostel) ---
class RoomAllocation(Base):
    __tablename__ = "room_allocations"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("hostel_rooms.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    allocation_date = Column(DateTime(timezone=True), nullable=False)
    room = relationship("HostelRoom", backref="allocations")
    student = relationship("User", backref="room_allocations")


# --- IoT: simulated sensors ---
class FacilityScope(str, enum.Enum):
    HOSTEL_ROOM = "hostel_room"
    OTHER_AREA = "other_area"


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, nullable=False, index=True)
    # hostel_room | other_area | or ThingsBoard facility_type label (e.g. "mens hostel")
    facility_scope = Column(String(200), nullable=False)
    # Optional label from ThingsBoard payload (e.g. room/site id as string)
    facility_name = Column(String(200), nullable=True)
    sensor_type = Column(String(50), nullable=False, index=True)
    value = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    thingsboard_device_id = Column(String(80), nullable=True, index=True)
    thingsboard_ts = Column(BigInteger, nullable=True)  # device telemetry ts (ms) for dedupe


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class SensorAlert(Base):
    __tablename__ = "sensor_alerts"
    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, nullable=False, index=True)
    facility_scope = Column(String(200), nullable=False)
    sensor_type = Column(String(50), nullable=False)
    alert_type = Column(String(80), nullable=False)
    reading_value = Column(String(100), nullable=True)  # value at trigger time (new alerts only)
    # Snapshot from reading at trigger time (ThingsBoard label / resolved name)
    facility_name = Column(String(200), nullable=True)
    # Primary UI label: room number or area/site name (no bare facility id)
    name_or_room_no = Column(String(200), nullable=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    status = Column(
        Enum(AlertStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=AlertStatus.OPEN,
        nullable=False,
    )


class NotificationCategory(str, enum.Enum):
    BOOKING = "booking"
    SENSOR = "sensor"
    SYSTEM = "system"
    EMERGENCY = "emergency"


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(String(2000), nullable=False)
    category = Column(String(40), nullable=False, default="system")
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user = relationship("User", backref="notifications")


# --- Maintenance & ticketing (broken assets) ---
class MaintenanceTicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MaintenanceScheduleStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaintenanceSchedule(Base):
    """Planned maintenance windows (facility manager / admin)."""
    __tablename__ = "maintenance_schedules"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    notes = Column(String(4000), nullable=True)
    hostel_room_id = Column(Integer, ForeignKey("hostel_rooms.id"), nullable=True)
    other_area_id = Column(Integer, ForeignKey("other_areas.id"), nullable=True)
    scheduled_start = Column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(
        Enum(MaintenanceScheduleStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=MaintenanceScheduleStatus.SCHEDULED,
        nullable=False,
    )
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    creator = relationship("User", foreign_keys=[created_by_id], backref="maintenance_schedules_created")
    hostel_room = relationship("HostelRoom", backref="maintenance_schedules")
    other_area = relationship("OtherArea", backref="maintenance_schedules")


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"
    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(4000), nullable=True)
    hostel_room_id = Column(Integer, ForeignKey("hostel_rooms.id"), nullable=True)
    other_area_id = Column(Integer, ForeignKey("other_areas.id"), nullable=True)
    status = Column(
        Enum(MaintenanceTicketStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=MaintenanceTicketStatus.OPEN,
        nullable=False,
    )
    photo_paths = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    reporter = relationship("User", foreign_keys=[reporter_id], backref="maintenance_tickets_reported")
    hostel_room = relationship("HostelRoom", backref="maintenance_tickets")
    other_area = relationship("OtherArea", backref="maintenance_tickets")
