from __future__ import annotations
"""Dining menu CRUD and facility-scoped inventory items (admin + read lists)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from . import models
from . import schemas
from .database import get_db
from .auth import verify_token, require_admin, require_admin_or_facility_manager

router = APIRouter(prefix="/campus", tags=["campus"])


# ---------- Dining menu (per other_area) ----------


@router.get(
    "/dining-areas/{other_area_id}/menu-items",
    response_model=list[schemas.DiningMenuItemResponse],
)
def list_dining_menu_items(
    other_area_id: int,
    meal_slot: str | None = Query(None, description="Filter: breakfast | lunch | dinner | snack"),
    diet_filter: str | None = Query(
        None,
        description="For booking UI: veg | non_veg — returns items with that diet or either",
    ),
    include_inactive: bool = Query(False, description="Admin: list inactive items too"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    area = db.query(models.OtherArea).filter(models.OtherArea.id == other_area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Dining area not found")
    q = db.query(models.DiningMenuItem).filter(models.DiningMenuItem.other_area_id == other_area_id)
    if meal_slot:
        q = q.filter(models.DiningMenuItem.meal_slot == meal_slot.lower())
    if not include_inactive or current_user.role not in (
        models.UserRole.ADMIN,
        models.UserRole.FACILITY_MANAGER,
    ):
        q = q.filter(models.DiningMenuItem.active.is_(True))
    df = (diet_filter or "").strip().lower()
    if df == "veg":
        q = q.filter(models.DiningMenuItem.diet.in_(("veg", "either")))
    elif df == "non_veg":
        q = q.filter(models.DiningMenuItem.diet.in_(("non_veg", "either")))
    elif diet_filter is not None and df not in ("", "veg", "non_veg"):
        raise HTTPException(status_code=400, detail="diet_filter must be veg or non_veg")
    return q.order_by(models.DiningMenuItem.meal_slot, models.DiningMenuItem.name).all()


@router.post(
    "/dining-areas/{other_area_id}/menu-items",
    response_model=schemas.DiningMenuItemResponse,
)
def create_dining_menu_item(
    other_area_id: int,
    body: schemas.DiningMenuItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    area = db.query(models.OtherArea).filter(models.OtherArea.id == other_area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Dining area not found")
    row = models.DiningMenuItem(
        other_area_id=other_area_id,
        meal_slot=body.meal_slot,
        name=body.name.strip(),
        description=(body.description or "").strip() or None,
        diet=body.diet,
        active=body.active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch(
    "/dining-menu-items/{item_id}",
    response_model=schemas.DiningMenuItemResponse,
)
def update_dining_menu_item(
    item_id: int,
    body: schemas.DiningMenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    row = db.query(models.DiningMenuItem).filter(models.DiningMenuItem.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Menu item not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "description" in data and data["description"] is not None:
        d = data["description"].strip()
        data["description"] = d or None
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/dining-menu-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dining_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    row = db.query(models.DiningMenuItem).filter(models.DiningMenuItem.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Menu item not found")
    db.delete(row)
    db.commit()
    return None


# ---------- Facility inventory (hostel room or other area) ----------


@router.get(
    "/facility-inventory-items",
    response_model=list[schemas.FacilityInventoryItemResponse],
)
def list_facility_inventory_items(
    hostel_room_id: int | None = Query(None),
    other_area_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(verify_token),
):
    if bool(hostel_room_id) == bool(other_area_id):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of hostel_room_id or other_area_id",
        )
    if hostel_room_id is not None:
        q = db.query(models.FacilityInventoryItem).filter(
            models.FacilityInventoryItem.facility_scope == "hostel_room",
            models.FacilityInventoryItem.facility_id == hostel_room_id,
        )
    else:
        q = db.query(models.FacilityInventoryItem).filter(
            models.FacilityInventoryItem.facility_scope == "other_area",
            models.FacilityInventoryItem.facility_id == other_area_id,
        )
    return q.order_by(models.FacilityInventoryItem.name).all()


@router.post(
    "/facility-inventory-items",
    response_model=schemas.FacilityInventoryItemResponse,
)
def create_facility_inventory_item(
    body: schemas.FacilityInventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if body.facility_scope == "hostel_room":
        room = db.query(models.HostelRoom).filter(models.HostelRoom.id == body.facility_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Hostel room not found")
    else:
        area = db.query(models.OtherArea).filter(models.OtherArea.id == body.facility_id).first()
        if not area:
            raise HTTPException(status_code=404, detail="Other area not found")
    row = models.FacilityInventoryItem(
        facility_scope=body.facility_scope,
        facility_id=body.facility_id,
        name=body.name.strip(),
        quantity_available=body.quantity_available,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch(
    "/facility-inventory-items/{item_id}",
    response_model=schemas.FacilityInventoryItemResponse,
)
def update_facility_inventory_item(
    item_id: int,
    body: schemas.FacilityInventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_or_facility_manager),
):
    row = (
        db.query(models.FacilityInventoryItem)
        .filter(models.FacilityInventoryItem.id == item_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/facility-inventory-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    row = (
        db.query(models.FacilityInventoryItem)
        .filter(models.FacilityInventoryItem.id == item_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    db.delete(row)
    db.commit()
    return None
