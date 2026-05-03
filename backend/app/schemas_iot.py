from __future__ import annotations
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Literal, Optional, Any, List, Dict


class SensorIngest(BaseModel):
    facility_id: int
    facility_scope: Literal["hostel_room", "other_area"]
    sensor_type: str
    value: str


class SensorReadingResponse(BaseModel):
    id: int
    facility_id: int
    facility_scope: str
    sensor_type: str
    value: str
    timestamp: datetime
    facility_name: Optional[str] = None
    thingsboard_device_id: Optional[str] = None
    thingsboard_ts: Optional[int] = None

    class Config:
        from_attributes = True


class ThingsBoardSyncRequest(BaseModel):
    """Optional overrides; defaults come from THINGSBOARD_* environment variables."""

    device_ids: Optional[List[str]] = None
    device_names: Optional[List[str]] = None
    telemetry_keys: Optional[List[str]] = None
    value_key: Optional[str] = None
    lookback_ms: int = 86_400_000


class SensorReadingEnriched(BaseModel):
    id: int
    facility_id: int
    facility_scope: str
    sensor_type: str
    value: str
    display_value: str
    timestamp: datetime
    facility_name: str
    facility_type_key: str
    facility_detail: Dict[str, Any]


class SensorAlertResponse(BaseModel):
    id: int
    facility_id: int
    facility_scope: str
    sensor_type: str
    alert_type: str
    triggered_at: datetime
    status: str

    @field_validator("status", mode="before")
    @classmethod
    def status_to_str(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)

    class Config:
        from_attributes = True


class SensorAlertEnriched(BaseModel):
    id: int
    facility_id: int
    facility_scope: str
    sensor_type: str
    alert_type: str
    triggered_at: datetime
    status: str
    reading_value: Optional[str] = None
    display_value: Optional[str] = None
    facility_name: str
    # Persisted at alert time for Name / Room No column
    name_or_room_no: Optional[str] = None
    facility_type_key: str
    facility_detail: Dict[str, Any]

    @field_validator("status", mode="before")
    @classmethod
    def status_to_str(cls, v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)


class AlertStatusUpdate(BaseModel):
    status: Literal["acknowledged", "resolved"]


class NotificationResponse(BaseModel):
    id: int
    title: str
    body: str
    category: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RoomAllocationCreate(BaseModel):
    room_id: int
    student_id: int
    allocation_date: datetime


class RoomAllocationResponse(BaseModel):
    id: int
    room_id: int
    student_id: int
    allocation_date: datetime

    class Config:
        from_attributes = True


class AnalyticsDashboard(BaseModel):
    bookings_total: int
    bookings_by_status: Dict[str, int]
    hostel_booking_count: int
    other_area_booking_count: int
    hostel_rooms_count: int
    other_areas_count: int
    sensor_readings: int
    open_sensor_alerts: int


class RoomInviteResponse(BaseModel):
    invites_sent: int
