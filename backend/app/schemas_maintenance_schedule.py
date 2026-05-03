"""Planned maintenance schedules (facility manager / admin)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class MaintenanceScheduleCreate(BaseModel):
    title: str
    notes: Optional[str] = None
    hostel_room_id: Optional[int] = None
    other_area_id: Optional[int] = None
    scheduled_start: datetime
    scheduled_end: datetime

    @model_validator(mode="after")
    def one_facility_and_times(self):
        if bool(self.hostel_room_id) == bool(self.other_area_id):
            raise ValueError("Provide exactly one of hostel_room_id or other_area_id")
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        return self


class MaintenanceScheduleUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: Optional[str] = None

    @model_validator(mode="after")
    def times(self):
        if self.scheduled_start is not None and self.scheduled_end is not None:
            if self.scheduled_end <= self.scheduled_start:
                raise ValueError("scheduled_end must be after scheduled_start")
        return self


class MaintenanceScheduleResponse(BaseModel):
    id: int
    title: str
    notes: Optional[str] = None
    hostel_room_id: Optional[int] = None
    other_area_id: Optional[int] = None
    facility_label: str
    facility_detail: Dict[str, Any] = Field(default_factory=dict)
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    created_by_id: int
    created_by_name: str
    created_at: datetime

    class Config:
        from_attributes = True
