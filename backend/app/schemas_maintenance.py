from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional, List, Dict

from pydantic import BaseModel, Field


class MaintenanceTicketCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=4000)
    hostel_room_id: Optional[int] = None
    other_area_id: Optional[int] = None


class MaintenanceTicketStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]


class MaintenanceTicketResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    hostel_room_id: Optional[int]
    other_area_id: Optional[int]
    facility_label: str
    facility_detail: Dict
    photo_urls: List[str]
    reporter_id: int
    reporter_name: str
    created_at: datetime

    class Config:
        from_attributes = True
