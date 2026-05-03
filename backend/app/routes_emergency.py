from __future__ import annotations
"""Emergency broadcast: in-app + email to all users of a selected role."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .auth import require_emergency_broadcast
from .services.notification_service import notify_emergency_to_role, is_smtp_configured

router = APIRouter(prefix="/emergency", tags=["emergency"])


class EmergencyBroadcastBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=4000)
    target_role: str = Field(
        ...,
        description='One of: "Admin", "Facility Manager", "Security", "Student", "Staff"',
    )


@router.post("/broadcast")
def emergency_broadcast(
    body: EmergencyBroadcastBody,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_emergency_broadcast),
):
    try:
        role = models.UserRole(body.target_role.strip())
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Invalid target_role",
        )
    title = "Emergency alert"
    n = notify_emergency_to_role(
        db,
        role,
        title,
        body.description.strip(),
        current_user.name,
    )
    return {
        "message": "Broadcast sent",
        "recipient_count": n,
        "target_role": role.value,
        "smtp_configured": is_smtp_configured(),
        "email_note": None
        if is_smtp_configured()
        else "Email not sent: set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM in .env (use SMTP_USE_SSL=true for port 465).",
    }
