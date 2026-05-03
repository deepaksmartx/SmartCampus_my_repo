from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models
from . import schemas
from .database import get_db
from .auth import verify_token, require_admin
import hashlib

router = APIRouter(prefix="/users", tags=["users"])


def _count_other_active_admins(db: Session, exclude_user_id: int) -> int:
    return (
        db.query(models.User)
        .filter(
            models.User.role == models.UserRole.ADMIN,
            models.User.is_active.is_(True),
            models.User.id != exclude_user_id,
        )
        .count()
    )


@router.patch("/profile", response_model=schemas.UserResponse)
def update_my_profile(
    body: schemas.UserProfileSelfUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    """Update year/department/membership (booking eligibility) and phone."""
    data = body.model_dump(exclude_unset=True)
    if not data:
        return current_user
    if "phone_number" in data:
        current_user.phone_number = data["phone_number"]
    if "year_of_study" in data:
        current_user.year_of_study = data["year_of_study"]
    if "department" in data:
        d = data["department"]
        current_user.department = (d.strip()[:120] if isinstance(d, str) and d.strip() else None)
    if "membership_tier" in data:
        current_user.membership_tier = data["membership_tier"]
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/profile", response_model=schemas.UserResponse)
def get_current_user_profile(current_user: models.User = Depends(verify_token)):
    """
    Fetch current authenticated user's profile
    
    Requires: Valid JWT token in Authorization header
    """
    return current_user


@router.get("/admin/users", response_model=list[schemas.UserResponse])
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    rows = db.query(models.User).order_by(models.User.id.asc()).all()
    return rows


@router.patch("/admin/users/{user_id}", response_model=schemas.UserResponse)
def admin_update_user(
    user_id: int,
    body: schemas.UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        return user

    if data.get("is_active") is False and user.id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")

    new_role = data.get("role")
    new_role_val = None
    if new_role is not None:
        new_role_val = new_role.value if hasattr(new_role, "value") else str(new_role)

    if new_role_val is not None and new_role_val != models.UserRole.ADMIN.value and user.role == models.UserRole.ADMIN:
        if _count_other_active_admins(db, user.id) < 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Cannot change the last administrator to a non-admin role",
            )

    if data.get("is_active") is False and user.role == models.UserRole.ADMIN:
        if _count_other_active_admins(db, user.id) < 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active administrator",
            )

    if "name" in data and data["name"] is not None:
        user.name = str(data["name"]).strip()[:100] or user.name
    if "phone_number" in data:
        user.phone_number = data["phone_number"]
    if new_role_val is not None:
        user.role = models.UserRole(new_role_val)
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = bool(data["is_active"])
    if "year_of_study" in data:
        user.year_of_study = data["year_of_study"]
    if "department" in data:
        d = data["department"]
        user.department = (d.strip()[:120] if isinstance(d, str) and d.strip() else None)
    if "membership_tier" in data:
        user.membership_tier = data["membership_tier"]

    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user_by_id(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    """
    Fetch user profile by user ID
    
    Requires: Valid JWT token in Authorization header
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    return user

@router.get("/email/{email}", response_model=schemas.UserResponse)
def get_user_by_email(email: str, db: Session = Depends(get_db), current_user: models.User = Depends(verify_token)):
    """
    Fetch user profile by email
    
    Requires: Valid JWT token in Authorization header
    """
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found"
        )
    
    return user

@router.post("/register")
def register_user(user: schemas.UserRegister, db: Session = Depends(get_db)):

    # check if email already exists
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = hashlib.sha256(user.password.encode()).hexdigest()

    # schemas.UserRole is not models.UserRole; coerce by value string so DB gets "Security" not "UserRole.SECURITY"
    role = models.UserRole(user.role.value)

    new_user = models.User(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password,
        role=role,
        phone_number=user.phone_number,
        is_active=True,
        year_of_study=user.year_of_study,
        department=(
            user.department.strip()[:120]
            if user.department and str(user.department).strip()
            else None
        ),
        membership_tier=user.membership_tier,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}