from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models
from .database import get_db
from .auth import verify_token
from .schemas_iot import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    unread_only: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    q = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
    )
    if unread_only:
        q = q.filter(models.Notification.read.is_(False))
    return q.limit(limit).all()


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    n = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id,
        )
        .first()
    )
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n.read = True
    db.commit()
    db.refresh(n)
    return n


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.read.is_(False),
    ).update({models.Notification.read: True}, synchronize_session=False)
    db.commit()
    return {"ok": True}
