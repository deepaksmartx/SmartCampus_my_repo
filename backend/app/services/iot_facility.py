from __future__ import annotations
"""Resolve sensor facility_id + scope to human-readable names and type keys."""
import re

from sqlalchemy.orm import Session, joinedload

from .. import models
from .iot_service import is_occupancy_sensor_type


def _format_reading_number(value: str) -> str:
    try:
        f = float(value)
        if f == int(f):
            return str(int(f))
        s = f"{f:.3f}".rstrip("0").rstrip(".")
        return s if s else str(f)
    except (TypeError, ValueError):
        return value


def _tb_facility_label_to_key(label: str) -> str:
    s = (label or "").lower().strip().replace("_", " ")
    if "men" in s and "hostel" in s:
        return "mens_hostel"
    if ("ladies" in s or "women" in s or "ladys" in s) and "hostel" in s:
        return "ladies_hostel"
    if "dining" in s or "mess" in s:
        return "dining"
    if "sport" in s:
        return "sports"
    if "academic" in s:
        return "academic_spaces"
    return "unknown"


def facility_type_key_from_hostel_room(hr: models.HostelRoom | None) -> str | None:
    if not hr or not hr.facility_type:
        return None
    n = hr.facility_type.name
    return n.value if hasattr(n, "value") else str(n)


def alert_name_or_room_from_info(
    info: dict, stored_facility_name: str | None
) -> str | None:
    """Single snapshot string for Name / Room No (room no, area name, or telemetry label)."""
    d = info.get("facility_detail") or {}
    kind = d.get("kind")
    if kind == "hostel_room":
        r = d.get("roomno")
        if r is not None and str(r).strip():
            return str(r).strip()
    elif kind == "other_area":
        n = d.get("name")
        if n and str(n).strip():
            return str(n).strip()
    elif kind == "thingsboard":
        for key in ("roomno", "name"):
            v = d.get(key)
            if v is not None and str(v).strip():
                return str(v).strip()
    sl = (stored_facility_name or "").strip()
    if sl and sl not in ("0", "00"):
        if re.match(r"^#\d+$", sl) or re.match(r"^ID\s*\d+$", sl, re.I):
            pass
        else:
            return sl.split("·")[0].strip() if "·" in sl else sl
    fn = (info.get("facility_name") or "").strip()
    if fn and not re.match(r"^Unknown (room|area) #", fn, re.I):
        if re.match(r"^#\d+$", fn) or re.match(r"^ID\s*\d+$", fn, re.I):
            return None
        return fn.split("·")[0].strip()
    return None


def facility_type_key_from_other_area(oa: models.OtherArea | None) -> str | None:
    if not oa or not oa.facility_type:
        return None
    n = oa.facility_type.name
    return n.value if hasattr(n, "value") else str(n)


def resolve_facility(
    db: Session,
    facility_id: int,
    facility_scope: str,
    stored_facility_name: str | None = None,
) -> dict:
    """
    Returns facility_name, facility_type_key, facility_detail (for UI popup).
    facility_type_key: mens_hostel | ladies_hostel | dining | sports | academic_spaces | unknown
    """
    if facility_scope == "hostel_room":
        hr = (
            db.query(models.HostelRoom)
            .options(
                joinedload(models.HostelRoom.building),
                joinedload(models.HostelRoom.floor),
                joinedload(models.HostelRoom.facility_type),
            )
            .filter(models.HostelRoom.id == facility_id)
            .first()
        )
        if not hr:
            sl = (stored_facility_name or "").strip()
            if sl:
                return {
                    "facility_name": sl,
                    "facility_type_key": "unknown",
                    "facility_detail": {
                        "kind": "hostel_room",
                        "roomno": sl,
                        "facility_id": facility_id,
                        "note": "Room not in campus list; label from sensor data",
                    },
                }
            return {
                "facility_name": f"Unknown room #{facility_id}",
                "facility_type_key": "unknown",
                "facility_detail": {"error": "hostel room not found", "facility_id": facility_id},
            }
        ft_key = facility_type_key_from_hostel_room(hr) or "unknown"
        bname = hr.building.name if hr.building else None
        floor_no = hr.floor.floor_no if hr.floor else None
        rt = hr.room_type.value if hasattr(hr.room_type, "value") else str(hr.room_type)
        detail = {
            "kind": "hostel_room",
            "id": hr.id,
            "roomno": hr.roomno,
            "room_type": rt,
            "facility_type": ft_key,
            "building": bname,
            "floor": floor_no,
            "capacity": hr.room_capacity,
        }
        name = f"{hr.roomno}" + (f" · {bname}" if bname else "")
        return {
            "facility_name": name,
            "facility_type_key": ft_key,
            "facility_detail": detail,
        }

    if facility_scope == "other_area":
        oa = (
            db.query(models.OtherArea)
            .options(
                joinedload(models.OtherArea.building),
                joinedload(models.OtherArea.floor),
                joinedload(models.OtherArea.facility_type),
            )
            .filter(models.OtherArea.id == facility_id)
            .first()
        )
        if not oa:
            sl = (stored_facility_name or "").strip()
            if sl:
                return {
                    "facility_name": sl,
                    "facility_type_key": "unknown",
                    "facility_detail": {
                        "kind": "other_area",
                        "name": sl,
                        "facility_id": facility_id,
                        "note": "Area not in campus list; label from sensor data",
                    },
                }
            return {
                "facility_name": f"Unknown area #{facility_id}",
                "facility_type_key": "unknown",
                "facility_detail": {"error": "other area not found", "facility_id": facility_id},
            }
        ft_key = facility_type_key_from_other_area(oa) or "unknown"
        bname = oa.building.name if oa.building else None
        floor_no = oa.floor.floor_no if oa.floor else None
        detail = {
            "kind": "other_area",
            "id": oa.id,
            "name": oa.name,
            "facility_type": ft_key,
            "building": bname,
            "floor": floor_no,
            "capacity": oa.capacity,
            "active": oa.active,
        }
        return {
            "facility_name": oa.name + (f" · {bname}" if bname else ""),
            "facility_type_key": ft_key,
            "facility_detail": detail,
        }

    ft_key = _tb_facility_label_to_key(facility_scope)
    label = _thingsboard_row_display_name(stored_facility_name, facility_id, facility_scope)
    return {
        "facility_name": label,
        "facility_type_key": ft_key,
        "facility_detail": {
            "kind": "thingsboard",
            "facility_type_label": facility_scope,
            "facility_id": facility_id,
        },
    }


def _thingsboard_row_display_name(
    stored_facility_name: str | None, facility_id: int, facility_scope: str
) -> str:
    """Avoid '#0' when there is no campus id; prefer telemetry label then a readable scope."""
    s = (stored_facility_name or "").strip()
    if s and s not in ("0", "00"):
        return s
    if facility_id > 0:
        return f"#{facility_id}"
    fs = (facility_scope or "").strip()
    if fs and fs.lower() != "unknown":
        return fs.replace("_", " ").title()
    return "—"


def display_sensor_value(sensor_type: str, value: str) -> str:
    st = (sensor_type or "").lower().strip()
    if is_occupancy_sensor_type(sensor_type or ""):
        try:
            return str(int(round(float(value))))
        except (TypeError, ValueError):
            return value

    v = _format_reading_number(value)

    if st in ("water", "water_l", "water_liters", "water_usage") or (
        "water" in st and "meter" in st
    ):
        return f"{v} L"

    if st in ("energy", "energy_kwh", "energy_usage", "power_kw") or (
        "energy" in st and "meter" in st
    ):
        return f"{v} kWh"

    if st in ("temp", "temperature", "temp_c") or "temperature" in st.replace(" ", ""):
        return f"{v} °C"

    return value


def matches_facility_type_filter(
    facility_type_key: str, facility_scope: str, filter_key: str | None
) -> bool:
    if not filter_key or filter_key == "all":
        return True
    fk = filter_key.lower().strip()
    if fk == "hostel":
        return facility_scope == "hostel_room" or facility_type_key in (
            "mens_hostel",
            "ladies_hostel",
        )
    return facility_type_key == fk
