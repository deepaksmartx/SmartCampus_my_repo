from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from enum import Enum
from typing import List, Optional, Any, Literal, Dict, Union

class UserRole(str, Enum):
    ADMIN = "Admin"
    FACILITY_MANAGER = "Facility Manager"
    SECURITY = "Security"
    STUDENT = "Student"
    STAFF = "Staff"

class UserResponse(BaseModel):
    """User profile response - excludes sensitive data like password"""
    id: int
    name: str
    email: str
    phone_number: Optional[str] = None
    role: UserRole
    is_active: bool = True
    profile_photo: Optional[str] = None
    year_of_study: Optional[int] = None
    department: Optional[str] = None
    membership_tier: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileSelfUpdate(BaseModel):
    """Student/staff: update profile fields used for booking eligibility."""
    year_of_study: Optional[int] = Field(None, ge=1, le=10)
    department: Optional[str] = Field(None, max_length=120)
    membership_tier: Optional[Literal["basic", "standard", "premium"]] = None
    phone_number: Optional[str] = None


class UserAdminUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    year_of_study: Optional[int] = Field(None, ge=1, le=10)
    department: Optional[str] = Field(None, max_length=120)
    membership_tier: Optional[Literal["basic", "standard", "premium"]] = None

class ErrorResponse(BaseModel):
    detail: str

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    phone_number: Optional[str] = None
    year_of_study: Optional[int] = Field(None, ge=1, le=10)
    department: Optional[str] = Field(None, max_length=120)
    membership_tier: Optional[Literal["basic", "standard", "premium"]] = None


# --- Campus / Building / Floor / Facility / OtherArea / HostelRoom schemas ---

class FacilityTypeName(str, Enum):
    mens_hostel = "mens_hostel"
    ladies_hostel = "ladies_hostel"
    dining = "dining"
    sports = "sports"
    academic_spaces = "academic_spaces"

class RoomType(str, Enum):
    Single = "Single"
    Double = "Double"
    Suite = "Suite"

# Campus
class CampusCreate(BaseModel):
    name: str
    location: Optional[str] = None

class CampusUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None

class CampusResponse(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    class Config:
        from_attributes = True

# Building
class BuildingCreate(BaseModel):
    name: str
    campus_id: int

class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    campus_id: Optional[int] = None

class BuildingResponse(BaseModel):
    id: int
    name: str
    campus_id: int
    class Config:
        from_attributes = True

# Floor
class FloorCreate(BaseModel):
    building_id: int
    floor_no: int

class FloorUpdate(BaseModel):
    building_id: Optional[int] = None
    floor_no: Optional[int] = None

class FloorResponse(BaseModel):
    id: int
    building_id: int
    floor_no: int
    class Config:
        from_attributes = True

# FacilityType
class FacilityTypeCreate(BaseModel):
    name: FacilityTypeName

class FacilityTypeResponse(BaseModel):
    id: int
    name: str  # FacilityTypeName value

    @field_validator("name", mode="before")
    @classmethod
    def name_to_str(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else v

    class Config:
        from_attributes = True

# OtherArea
class OtherAreaCreate(BaseModel):
    name: str
    building_id: int
    floor_id: int
    capacity: Optional[int] = None
    facility_type_id: int
    active: bool = True
    staff_only: bool = False
    eligibility_rules: Optional[Dict[str, Any]] = None

class OtherAreaUpdate(BaseModel):
    name: Optional[str] = None
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    capacity: Optional[int] = None
    facility_type_id: Optional[int] = None
    active: Optional[bool] = None
    staff_only: Optional[bool] = None
    eligibility_rules: Optional[Dict[str, Any]] = None

class OtherAreaResponse(BaseModel):
    id: int
    name: str
    building_id: int
    floor_id: int
    capacity: Optional[int] = None
    facility_type_id: int
    active: bool
    staff_only: bool
    eligibility_rules: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# HostelRoom
class HostelRoomCreate(BaseModel):
    roomno: str
    room_type: RoomType
    facility_type_id: int
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    inmate_profiles: Optional[List[int]] = None
    room_capacity: int
    staff_only: bool = False
    eligibility_rules: Optional[Dict[str, Any]] = None

class HostelRoomUpdate(BaseModel):
    roomno: Optional[str] = None
    room_type: Optional[RoomType] = None
    facility_type_id: Optional[int] = None
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    inmate_profiles: Optional[List[int]] = None
    room_capacity: Optional[int] = None
    staff_only: Optional[bool] = None
    eligibility_rules: Optional[Dict[str, Any]] = None

class HostelRoomResponse(BaseModel):
    id: int
    roomno: str
    room_type: str  # Single, Double, Suite
    facility_type_id: int
    building_id: Optional[int] = None
    floor_id: Optional[int] = None
    inmate_profiles: Optional[List[int]] = None
    room_capacity: int
    staff_only: bool
    eligibility_rules: Optional[Dict[str, Any]] = None

    @field_validator("room_type", mode="before")
    @classmethod
    def room_type_to_str(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else v

    @field_validator("eligibility_rules", mode="before")
    @classmethod
    def eligibility_rules_coerce(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None or v == {}:
            return None
        return v if isinstance(v, dict) else None

    class Config:
        from_attributes = True


class HostelRoomWithLiveCount(HostelRoomResponse):
    """List view: includes how many distinct users have a booking active right now (UTC)."""

    live_booking_count: int = Field(0, ge=0)


# Booking
class BookingStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"

class BookingUserBrief(BaseModel):
    id: int
    name: str
    email: str
    phone_number: Optional[str] = None
    role: str


class HostelRoomLiveOccupancyResponse(BaseModel):
    room_id: int
    registered_inmates: List[BookingUserBrief]
    active_bookers: List[BookingUserBrief]


class InventorySelectionLine(BaseModel):
    inventory_item_id: int
    quantity: int = Field(ge=1)


MealSlotLiteral = Literal["breakfast", "lunch", "dinner", "snack"]


class BookingCreate(BaseModel):
    hostel_room_id: Optional[int] = None
    other_area_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    meal_preference: Optional[Literal["veg", "non_veg"]] = None
    meal_slot: Optional[MealSlotLiteral] = None
    dining_menu_item_ids: Optional[List[int]] = None
    inventory_selections: Optional[List[InventorySelectionLine]] = None
    # Non-hostel only, Staff only (enforced in API): VIP; overlapping normals removed when Admin/FM accepts
    request_vip: bool = False

class BookingReviewUpdate(BaseModel):
    status: Literal["accepted", "rejected"]

class BookingPriorityUpdate(BaseModel):
    priority: Literal["normal", "vip"]


class BookingTimesUpdate(BaseModel):
    start_time: datetime
    end_time: datetime

class BookingResponse(BaseModel):
    id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: str
    priority: str = "normal"
    created_at: Optional[datetime] = None
    hostel_room_id: Optional[int] = None
    other_area_id: Optional[int] = None
    meal_preference: Optional[str] = None
    meal_slot: Optional[str] = None
    dining_menu_item_ids: List[int] = Field(default_factory=list)
    inventory_selections: List[Dict[str, Any]] = Field(default_factory=list)
    user: Optional[BookingUserBrief] = None

    @field_validator("status", mode="before")
    @classmethod
    def status_to_str(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else v

    @field_validator("priority", mode="before")
    @classmethod
    def priority_to_str(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v or "normal")

    @field_validator("dining_menu_item_ids", mode="before")
    @classmethod
    def menu_ids_coerce(cls, v: Any) -> List[int]:
        if not v or not isinstance(v, list):
            return []
        out: List[int] = []
        for x in v:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out

    @field_validator("inventory_selections", mode="before")
    @classmethod
    def inv_sel_coerce(cls, v: Any) -> List[Dict[str, Any]]:
        if not v or not isinstance(v, list):
            return []
        return [x for x in v if isinstance(x, dict)]

    class Config:
        from_attributes = True


# --- Dining menu & facility inventory (admin CRUD + reads) ---

class DiningMenuItemCreate(BaseModel):
    meal_slot: MealSlotLiteral
    name: str
    description: Optional[str] = None
    diet: Literal["veg", "non_veg", "either"] = "either"
    active: bool = True


class DiningMenuItemUpdate(BaseModel):
    meal_slot: Optional[MealSlotLiteral] = None
    name: Optional[str] = None
    description: Optional[str] = None
    diet: Optional[Literal["veg", "non_veg", "either"]] = None
    active: Optional[bool] = None


class DiningMenuItemResponse(BaseModel):
    id: int
    other_area_id: int
    meal_slot: str
    name: str
    description: Optional[str] = None
    diet: str
    active: bool

    class Config:
        from_attributes = True


class FacilityInventoryItemCreate(BaseModel):
    facility_scope: Literal["hostel_room", "other_area"]
    facility_id: int
    name: str
    quantity_available: int = Field(ge=0)


class FacilityInventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity_available: Optional[int] = Field(default=None, ge=0)


class FacilityInventoryItemResponse(BaseModel):
    id: int
    facility_scope: str
    facility_id: int
    name: str
    quantity_available: int

    class Config:
        from_attributes = True


class HostelRoomBookingPreview(BaseModel):
    room_id: int
    room_capacity: int
    overlapping_booking_count: int
    slots_remaining: int
    registered_inmates: List[BookingUserBrief]
    booking_occupants: List[BookingUserBrief]