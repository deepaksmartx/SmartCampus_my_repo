from __future__ import annotations
"""In-app and email notifications for bookings and sensor alerts."""
import logging
import os
import smtplib
from email.mime.text import MIMEText
from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)

# Log once per process if SMTP is unset (avoids spam on every notification)
_smtp_missing_logged = False


def is_smtp_configured() -> bool:
    """True when SMTP_HOST is set; otherwise emails are skipped."""
    return bool(os.getenv("SMTP_HOST", "").strip())


def _send_smtp(to_email: str, subject: str, body: str) -> bool:
    global _smtp_missing_logged
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        if not _smtp_missing_logged:
            logger.warning(
                "SMTP_HOST is not set — email notifications are disabled. "
                "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD (and SMTP_FROM) in .env to enable mail.",
            )
            _smtp_missing_logged = True
        return False
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_addr = os.getenv("SMTP_FROM", user or "noreply@smartcampus.local")
    # Port 465 typically uses implicit TLS; 587 uses STARTTLS
    use_ssl = os.getenv("SMTP_USE_SSL", "").strip().lower() in ("1", "true", "yes")
    skip_starttls = os.getenv("SMTP_SKIP_STARTTLS", "").strip().lower() in ("1", "true", "yes")
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.sendmail(from_addr, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if not skip_starttls:
                    smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except Exception as e:
        logger.warning("SMTP send failed for %s: %s", to_email, e)
        return False


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    category: str = models.NotificationCategory.SYSTEM.value,
    send_email: bool = True,
) -> models.Notification:
    n = models.Notification(
        user_id=user_id,
        title=title[:200],
        body=body[:2000],
        category=category,
        read=False,
    )
    db.add(n)
    db.flush()
    if send_email:
        u = db.query(models.User).filter(models.User.id == user_id).first()
        if u and u.email:
            _send_smtp(u.email, f"[SmartCampus] {title[:200]}", body[:8000])
    return n


def notify_booking_displaced_by_vip(
    db: Session,
    *,
    displaced_user_id: int,
    rejected_booking_id: int,
    facility_name: str,
    start_time,
    end_time,
) -> None:
    """In-app + email when a normal booking is rejected for a VIP slot takeover."""
    try:
        st = start_time.strftime("%Y-%m-%d %H:%M UTC") if start_time else ""
        en = end_time.strftime("%Y-%m-%d %H:%M UTC") if end_time else ""
    except Exception:
        st, en = str(start_time), str(end_time)
    create_notification(
        db,
        displaced_user_id,
        "Booking rejected — VIP priority",
        (
            f"Your booking #{rejected_booking_id} for «{facility_name}» ({st} – {en}) was rejected "
            f"automatically because a VIP booking for the same time slot was accepted by administration."
        )[:2000],
        category=models.NotificationCategory.BOOKING.value,
    )


def notify_users_email(db: Session, user_ids: list[int], subject: str, body: str) -> None:
    users = db.query(models.User).filter(models.User.id.in_(user_ids)).all()
    for u in users:
        if u.email:
            _send_smtp(u.email, subject, body)


def iter_admin_and_fm_ids(db: Session) -> list[int]:
    rows = (
        db.query(models.User.id)
        .filter(
            models.User.role.in_(
                (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER)
            )
        )
        .all()
    )
    return [r[0] for r in rows]


def notify_admins_fm_in_app(db: Session, title: str, body: str, category: str) -> None:
    for uid in iter_admin_and_fm_ids(db):
        create_notification(db, uid, title, body, category)
    db.commit()


def notify_booking_created(db: Session, booking: models.Booking, booker: models.User) -> None:
    res = (
        f"Hostel room #{booking.hostel_room_id}"
        if booking.hostel_room_id
        else f"Area #{booking.other_area_id}"
    )
    create_notification(
        db,
        booker.id,
        "Booking request submitted",
        f"Your booking ({res}) is pending approval.",
        models.NotificationCategory.BOOKING.value,
    )
    admin_ids = iter_admin_and_fm_ids(db)
    for uid in admin_ids:
        create_notification(
            db,
            uid,
            "New booking pending review",
            f"Booking #{booking.id} from {booker.name} ({booker.email}) — {res}.",
            models.NotificationCategory.BOOKING.value,
        )
    db.commit()


def notify_booking_reviewed(db: Session, booking: models.Booking) -> None:
    u = db.query(models.User).filter(models.User.id == booking.user_id).first()
    if not u:
        return
    if booking.status == models.BookingStatus.ACCEPTED:
        title, msg = "Booking accepted", f"Your booking #{booking.id} has been accepted."
    else:
        title, msg = "Booking rejected", f"Your booking #{booking.id} has been rejected."
    create_notification(db, u.id, title, msg, models.NotificationCategory.BOOKING.value)
    db.commit()


def notify_sensor_alert(
    db: Session,
    alert: models.SensorAlert,
    detail: str,
) -> None:
    scope = alert.facility_scope
    title = f"Sensor alert: {alert.alert_type}"
    body = (
        f"Facility {scope} id={alert.facility_id}, sensor={alert.sensor_type}. {detail}"
    )
    ids = iter_admin_and_fm_ids(db)
    for uid in ids:
        create_notification(db, uid, title, body, models.NotificationCategory.SENSOR.value)
    db.commit()


def notify_emergency_to_role(
    db: Session,
    target_role: models.UserRole,
    title: str,
    body: str,
    sender_name: str,
) -> int:
    """In-app + email to all active users with the given role."""
    users = (
        db.query(models.User)
        .filter(models.User.role == target_role, models.User.is_active.is_(True))
        .all()
    )
    extra = f"\n\n— Sent by {sender_name}"
    full_body = (body.strip()[:1900] + extra)[:2000]
    for u in users:
        create_notification(
            db,
            u.id,
            title[:200],
            full_body,
            models.NotificationCategory.EMERGENCY.value,
        )
    db.commit()
    return len(users)
