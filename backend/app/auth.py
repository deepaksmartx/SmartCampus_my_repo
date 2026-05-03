from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
from dotenv import load_dotenv
from . import models
from .database import get_db

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

security = HTTPBearer()

def verify_token(credentials = Depends(security), db: Session = Depends(get_db)):
    """Verify JWT token from Authorization header and return the user"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))  # Convert back to int
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if getattr(user, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user

def require_admin(current_user: models.User = Depends(verify_token)):
    """Require current user to be Admin. Use for create/delete."""
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

def require_admin_or_facility_manager(current_user: models.User = Depends(verify_token)):
    """Require Admin or Facility Manager. Use for update."""
    if current_user.role not in (models.UserRole.ADMIN, models.UserRole.FACILITY_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or Facility Manager access required")
    return current_user


def require_student_or_staff(current_user: models.User = Depends(verify_token)):
    """Require Student or Staff. Used for all booking actions (create, time changes); same rules including conflict checks."""
    if current_user.role not in (models.UserRole.STUDENT, models.UserRole.STAFF):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Booking is only available for Student or Staff")
    return current_user


def require_iot_dashboard_access(current_user: models.User = Depends(verify_token)):
    """Admin, Facility Manager, or Security (occupancy-only IoT on the backend)."""
    if current_user.role not in (
        models.UserRole.ADMIN,
        models.UserRole.FACILITY_MANAGER,
        models.UserRole.SECURITY,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IoT dashboard access required",
        )
    return current_user


def require_emergency_broadcast(current_user: models.User = Depends(verify_token)):
    """Send campus-wide emergency in-app (+ email) alerts."""
    if current_user.role not in (
        models.UserRole.ADMIN,
        models.UserRole.FACILITY_MANAGER,
        models.UserRole.SECURITY,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to send emergency broadcasts",
        )
    return current_user

def create_access_token(user_id: int, expires_delta: timedelta | None = None):
    """Create JWT access token"""
    to_encode = {"sub": str(user_id)}  # Convert to string
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
