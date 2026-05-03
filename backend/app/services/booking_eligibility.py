"""
Rule-based booking eligibility (facility JSON + user profile).

Facility `eligibility_rules` (optional JSON on hostel_rooms / other_areas):
- min_year, max_year (int): applied to Students only; Staff skip year checks.
- allowed_departments (list[str]): if non-empty, user's department must match (case-insensitive).
- min_membership: "basic" | "standard" | "premium" — user must be at this tier or higher.

Empty / null rules → no eligibility restriction from this layer.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from .. import models

MEMBERSHIP_ORDER = {"basic": 0, "standard": 1, "premium": 2}


def _tier_rank(tier: str | None) -> int:
    if not tier:
        return MEMBERSHIP_ORDER["basic"]
    k = str(tier).strip().lower()
    return MEMBERSHIP_ORDER.get(k, MEMBERSHIP_ORDER["basic"])


def _norm_dept(s: str | None) -> str:
    return (s or "").strip().lower()


def _rules_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def assert_user_eligible_for_booking(
    user: models.User,
    rules_raw: Any,
    *,
    facility_label: str = "this facility",
) -> None:
    rules = _rules_dict(rules_raw)
    if not rules:
        return

    role = user.role
    role_val = role.value if hasattr(role, "value") else str(role)

    # --- Year of study (students only) ---
    min_y = rules.get("min_year")
    max_y = rules.get("max_year")
    has_year_rule = min_y is not None or max_y is not None
    if has_year_rule and role_val == models.UserRole.STUDENT.value:
        y = getattr(user, "year_of_study", None)
        if y is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Year of study is required on your profile to book {facility_label}",
            )
        try:
            yi = int(y)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid year of study on your profile",
            )
        if min_y is not None and yi < int(min_y):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not eligible for {facility_label} (year of study below minimum)",
            )
        if max_y is not None and yi > int(max_y):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not eligible for {facility_label} (year of study above maximum)",
            )

    # --- Department allow-list ---
    allowed = rules.get("allowed_departments")
    if isinstance(allowed, list) and len(allowed) > 0:
        udept = _norm_dept(getattr(user, "department", None))
        if not udept:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Department is required on your profile to book {facility_label}",
            )
        allowed_l = {_norm_dept(x) for x in allowed if x is not None and str(x).strip()}
        if udept not in allowed_l:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not eligible for {facility_label} (department not permitted)",
            )

    # --- Membership tier ---
    min_m = rules.get("min_membership")
    if min_m is not None and str(min_m).strip():
        need = str(min_m).strip().lower()
        need_rank = MEMBERSHIP_ORDER.get(need)
        if need_rank is None:
            return
        utier = getattr(user, "membership_tier", None)
        if _tier_rank(utier) < need_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not eligible for {facility_label} (membership tier must be {need} or higher)",
            )
