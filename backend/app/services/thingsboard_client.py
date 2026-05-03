"""ThingsBoard tenant REST API: JWT login + device telemetry timeseries."""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _tb_base_url() -> str:
    u = os.getenv("THINGSBOARD_BASE_URL", "https://thingsboard.cloud").strip().rstrip("/")
    # POST to http://… often gets 302→https; urllib may follow with GET and drop the JSON body.
    # ThingsBoard then returns 401 "Authentication method not supported" (errorCode 10).
    low = u.lower()
    if low.startswith("http://thingsboard.cloud"):
        u = "https://" + u[len("http://") :]
    return u.rstrip("/")


def _ssl_context_for_url(base: str) -> ssl.SSLContext | None:
    """Only pass SSL context for https; avoids edge cases on Windows for plain http."""
    if base.lower().startswith("https://"):
        return ssl.create_default_context()
    return None


def _urlopen(req: urllib.request.Request, *, timeout: int):
    ctx = _ssl_context_for_url(_tb_base_url())
    kwargs: dict = {"timeout": timeout}
    if ctx is not None:
        kwargs["context"] = ctx
    return urllib.request.urlopen(req, **kwargs)


def tb_login(username: str, password: str, timeout: int = 60) -> str:
    base = _tb_base_url()
    body = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            raise RuntimeError(
                "ThingsBoard rejected login (401). Use your ThingsBoard tenant account "
                "(THINGSBOARD_USERNAME / THINGSBOARD_PASSWORD), not the device access token or SmartCampus JWT. "
                f"Check THINGSBOARD_BASE_URL ({base!r}). ThingsBoard response: {detail[:400]}"
            ) from e
        raise RuntimeError(
            f"ThingsBoard login failed: HTTP {e.code} {detail[:400]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"ThingsBoard login network error: {e}") from e
    token = data.get("token")
    if not token:
        raise RuntimeError("ThingsBoard login response missing token")
    return str(token)


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "X-Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _device_uuid_row(dev: dict[str, Any]) -> str:
    did = dev.get("id")
    if isinstance(did, dict):
        return str(did.get("id") or "")
    return str(did) if did is not None else ""


def find_device_id_by_name(token: str, device_name: str, timeout: int = 60) -> str | None:
    base = _tb_base_url()
    want = device_name.strip().lower()
    page = 0
    page_size = 50
    while page < 40:
        qs = urllib.parse.urlencode(
            {
                "page": page,
                "pageSize": page_size,
                "textSearch": device_name.strip(),
            }
        )
        url = f"{base}/api/tenant/devices?{qs}"
        req = urllib.request.Request(url, headers=_auth_headers(token), method="GET")
        try:
            with _urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"ThingsBoard list devices failed: HTTP {e.code} {e.read().decode('utf-8', errors='replace')}"
            ) from e
        rows = payload.get("data") or []
        for dev in rows:
            name = (dev.get("name") or "").strip().lower()
            if name == want:
                uid = _device_uuid_row(dev)
                if uid:
                    return uid
        if len(rows) < page_size:
            break
        page += 1
    return None


def fetch_timeseries(
    token: str,
    device_id: str,
    keys: list[str],
    start_ts_ms: int,
    end_ts_ms: int,
    limit: int = 100,
    timeout: int = 60,
) -> dict[str, list[dict[str, Any]]]:
    base = _tb_base_url()
    qs = urllib.parse.urlencode(
        {
            "keys": ",".join(keys),
            "startTs": start_ts_ms,
            "endTs": end_ts_ms,
            "limit": limit,
        }
    )
    url = f"{base}/api/plugins/telemetry/DEVICE/{urllib.parse.quote(device_id)}/values/timeseries?{qs}"
    req = urllib.request.Request(url, headers=_auth_headers(token), method="GET")
    try:
        with _urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"ThingsBoard telemetry failed: HTTP {e.code} {e.read().decode('utf-8', errors='replace')}"
        ) from e


def now_ms() -> int:
    return int(time.time() * 1000)
