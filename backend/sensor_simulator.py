"""
Simulated campus sensors: POST readings to POST /iot/ingest every 120 seconds.

Requires backend env IOT_INGEST_API_KEY to match header X-IoT-Key.

Usage (from backend dir):
  set IOT_INGEST_API_KEY=your-key
  python sensor_simulator.py

Optional env:
  API_BASE=http://127.0.0.1:8000
  IOT_SIM_INTERVAL_SEC=120
  IOT_SIM_HOSTEL_ROOM_ID=1
  IOT_SIM_OTHER_AREA_ID=1
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def post_ingest(base: str, key: str, payload: dict) -> None:
    url = f"{base.rstrip('/')}/iot/ingest"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-IoT-Key": key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> int:
    base = os.getenv("API_BASE", "http://127.0.0.1:8000").strip()
    key = os.getenv("IOT_INGEST_API_KEY", "").strip()
    interval = int(os.getenv("IOT_SIM_INTERVAL_SEC", "120"))
    hostel_id = int(os.getenv("IOT_SIM_HOSTEL_ROOM_ID", "1"))
    area_id = int(os.getenv("IOT_SIM_OTHER_AREA_ID", "1"))

    if not key:
        print("Set IOT_INGEST_API_KEY to match the backend.", file=sys.stderr)
        return 1

    tick = 0
    print(f"Sensor simulator → {base}/iot/ingest every {interval}s (Ctrl+C to stop)")
    while True:
        tick += 1
        # Normal readings; periodic spikes to trip energy/water thresholds (no temperature sensor)
        energy = random.uniform(50, 400)
        water = random.uniform(10, 120)
        occ = random.randint(0, 1)
        if tick % 7 == 0:
            energy = 950.0
        if tick % 11 == 0:
            water = 350.0

        batch = [
            {
                "facility_id": hostel_id,
                "facility_scope": "hostel_room",
                "sensor_type": "energy_kwh",
                "value": str(round(energy, 2)),
            },
            {
                "facility_id": hostel_id,
                "facility_scope": "hostel_room",
                "sensor_type": "water_l",
                "value": str(round(water, 1)),
            },
            {
                "facility_id": area_id,
                "facility_scope": "other_area",
                "sensor_type": "occupancy",
                "value": str(occ),
            },
        ]
        ts = datetime.now(timezone.utc).isoformat()
        for p in batch:
            try:
                post_ingest(base, key, p)
                print(f"[{ts}] OK {p['facility_scope']} id={p['facility_id']} {p['sensor_type']}={p['value']}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                print(f"[{ts}] HTTP {e.code} {p}: {body}", file=sys.stderr)
            except Exception as e:
                print(f"[{ts}] Error {p}: {e}", file=sys.stderr)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
