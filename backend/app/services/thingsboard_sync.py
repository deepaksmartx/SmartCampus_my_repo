"""Map ThingsBoard telemetry into SensorReading rows."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from .. import models
from . import thingsboard_client as tb
from .iot_service import persist_thingsboard_reading


def _latest_point(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not series:
        return None
    return max(series, key=lambda x: int(x.get("ts") or 0))


def _value_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v)


def merge_telemetry_rows(
    by_key: dict[str, list[dict[str, Any]]],
    value_key: str,
) -> tuple[dict[str, str], int] | None:
    anchor_series = by_key.get(value_key) or []
    anchor = _latest_point(anchor_series)
    if not anchor:
        return None
    t_anchor = int(anchor["ts"])
    out: dict[str, str] = {}

    for k, series in by_key.items():
        if not series:
            continue
        exact = [p for p in series if int(p.get("ts") or 0) == t_anchor]
        if exact:
            out[k] = _value_str(exact[0].get("value"))
            continue
        before = [p for p in series if int(p.get("ts") or 0) <= t_anchor]
        if before:
            best = max(before, key=lambda x: int(x.get("ts") or 0))
            out[k] = _value_str(best.get("value"))

    out.setdefault(value_key, _value_str(anchor.get("value")))
    return out, t_anchor


def _parse_facility_id(facility_name: str) -> int:
    s = (facility_name or "").strip()
    if not s or s in ("0", "00"):
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _telemetry_facility_label_and_id(fields: dict[str, str]) -> tuple[str | None, int]:
    """
    DB facility_name + id for ThingsBoard rows.
    Prefer facility_name; if missing or only '0', try common alternate telemetry keys.
    """
    raw = (fields.get("facility_name") or "").strip()
    alt = ""
    for k in (
        "room_name",
        "area_name",
        "site_name",
        "location",
        "facility_label",
        "place_name",
        "building_name",
    ):
        v = fields.get(k)
        if v is not None and str(v).strip():
            alt = str(v).strip()
            break
    if raw and raw not in ("0", "00"):
        label = raw
    else:
        label = alt or None
    fid = _parse_facility_id(raw)
    if fid == 0:
        fid = _parse_facility_id(alt)
    return label, fid


def _default_keys() -> list[str]:
    # Request all metrics you use across devices; TB returns only keys that exist per device.
    raw = os.getenv(
        "THINGSBOARD_TELEMETRY_KEYS",
        "water_usage,energy_usage,energyUsage,energy_kwh,power_kw,occupancy,temperature,temp,temp_c,"
        "device_name,facility_type,facility_name,room_name,area_name,site_name,location,"
        "facility_label,place_name,building_name",
    )
    return [k.strip() for k in raw.split(",") if k.strip()]


def _value_key_candidates() -> list[str]:
    """Try in order until one device has recent points (one primary metric per device)."""
    raw = os.getenv("THINGSBOARD_VALUE_KEYS", "").strip()
    if raw:
        return [k.strip() for k in raw.split(",") if k.strip()]
    vk = os.getenv("THINGSBOARD_VALUE_KEY", "").strip()
    if vk:
        return [vk]
    # Water meter → water_usage; Energy meter → energy_usage; Occupancy → occupancy
    return [
        "water_usage",
        "energy_usage",
        "energyUsage",
        "occupancy",
        "energy_kwh",
        "power_kw",
        "temperature",
        "temp",
        "temp_c",
    ]


def merge_telemetry_rows_flexible(
    by_key: dict[str, list[dict[str, Any]]],
    value_key_candidates: list[str],
) -> tuple[dict[str, str], int, str] | None:
    for vk in value_key_candidates:
        merged = merge_telemetry_rows(by_key, vk)
        if merged:
            fields, ts_ms = merged
            val = fields.get(vk, "").strip()
            if val != "":
                return fields, ts_ms, vk
    return None


def _gather_device_requests(
    requested_ids: list[str] | None, requested_names: list[str] | None
) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    if requested_ids:
        ids.extend([i.strip() for i in requested_ids if i.strip()])
    for part in os.getenv("THINGSBOARD_DEVICE_ID", "").split(","):
        p = part.strip()
        if p and p not in ids:
            ids.append(p)
    for part in os.getenv("THINGSBOARD_DEVICE_IDS", "").split(","):
        p = part.strip()
        if p and p not in ids:
            ids.append(p)
    names: list[str] = []
    if requested_names:
        names.extend([n.strip() for n in requested_names if n.strip()])
    env_name = os.getenv("THINGSBOARD_DEVICE_NAME", "").strip()
    if env_name and env_name not in names:
        names.append(env_name)
    return ids, names


def sync_thingsboard_telemetry(
    db: Session,
    *,
    device_ids: list[str] | None = None,
    device_names: list[str] | None = None,
    telemetry_keys: list[str] | None = None,
    value_key: str | None = None,
    lookback_ms: int = 86_400_000,
) -> list[models.SensorReading]:
    user = os.getenv("THINGSBOARD_USERNAME", "").strip()
    password = os.getenv("THINGSBOARD_PASSWORD", "").strip()
    if not user or not password:
        raise ValueError("Set THINGSBOARD_USERNAME and THINGSBOARD_PASSWORD for tenant API access")

    keys = telemetry_keys if telemetry_keys else _default_keys()
    value_key_candidates = _value_key_candidates()
    if value_key:
        value_key_candidates = [value_key.strip(), *value_key_candidates]
        value_key_candidates = list(dict.fromkeys(k for k in value_key_candidates if k))
    for vk in value_key_candidates:
        if vk not in keys:
            keys.append(vk)

    raw_ids, lookup_names = _gather_device_requests(device_ids, device_names)
    token = tb.tb_login(user, password)
    resolved: list[str] = list(raw_ids)
    for name in lookup_names:
        did = tb.find_device_id_by_name(token, name)
        if not did:
            raise ValueError(f"ThingsBoard device not found with name={name!r}")
        if did not in resolved:
            resolved.append(did)

    if not resolved:
        raise ValueError(
            "No ThingsBoard device id: pass device_ids / device_names or set "
            "THINGSBOARD_DEVICE_ID / THINGSBOARD_DEVICE_NAME"
        )

    end = tb.now_ms()
    start = end - max(60_000, lookback_ms)
    out_readings: list[models.SensorReading] = []

    for did in resolved:
        raw = tb.fetch_timeseries(token, did, keys, start, end)
        merged = merge_telemetry_rows_flexible(raw, value_key_candidates)
        if not merged:
            logger.warning(
                "ThingsBoard sync skipped device %s: no data for value keys %s in the last window "
                "(check telemetry key names and THINGSBOARD_TELEMETRY_KEYS / THINGSBOARD_VALUE_KEYS). "
                "Keys returned from TB: %s",
                did,
                value_key_candidates,
                list(raw.keys()),
            )
            continue
        fields, ts_ms, vk_used = merged
        facility_type = fields.get("facility_type") or ""
        device_name = fields.get("device_name") or "thingsboard_device"
        value = fields.get(vk_used, "")
        if value == "":
            continue
        facility_label, fid = _telemetry_facility_label_and_id(fields)
        ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        reading = persist_thingsboard_reading(
            db,
            facility_id=fid,
            facility_scope=facility_type.strip() or "unknown",
            facility_name=facility_label,
            sensor_type=device_name.strip(),
            value=value,
            timestamp=ts,
            thingsboard_device_id=did,
            thingsboard_ts=ts_ms,
        )
        out_readings.append(reading)

    return out_readings
