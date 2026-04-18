#!/usr/bin/env python3
"""
Geocode venue addresses via the US Census Geocoder batch API and add
`lat`/`lon` fields to /Users/graham/Projects/homegrown/homegrown_2026_venues.json.

Census Geocoder is free, no-auth, authoritative for US addresses. Batch
endpoint takes up to 10,000 rows per call; we have 40. One POST.

Source: https://geocoding.geo.census.gov/geocoder/
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
VENUES = ROOT / "homegrown_2026_venues.json"
ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

ADDR_RE = re.compile(r"^(.+?),\s*([^,]+),\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?$")


def split_address(full: str):
    m = ADDR_RE.match(full.strip())
    if not m:
        return None
    street = m.group(1)
    # Strip any suite/unit trailing on the street line — Census batch dislikes them.
    street = re.sub(r"\s+(Ste|Suite|Unit|#)\s*\S+.*$", "", street, flags=re.IGNORECASE)
    return street, m.group(2).strip(), m.group(3), m.group(4)


def build_batch_csv(venues):
    buf = io.StringIO()
    w = csv.writer(buf)
    for i, v in enumerate(venues):
        parts = split_address(v["address"] or "")
        if not parts:
            continue
        street, city, state, zipc = parts
        w.writerow([i, street, city, state, zipc])
    return buf.getvalue()


def post_batch(csv_text: str) -> str:
    boundary = "----census-batch-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="addressFile"; filename="addr.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_text}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="benchmark"\r\n\r\n'
        f"Public_AR_Current\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "homegrown-geocoder/1.0 (graham@snapstream.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_results(csv_text: str) -> dict[int, tuple[float, float]]:
    # Columns (no header): id, input, match, exact, matched_addr, coords, tigerline_id, side
    out: dict[int, tuple[float, float]] = {}
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) < 6:
            continue
        try:
            idx = int(row[0])
        except ValueError:
            continue
        if row[2] != "Match":
            continue
        coords = row[5]
        if "," not in coords:
            continue
        lon, lat = coords.split(",", 1)
        out[idx] = (float(lat), float(lon))
    return out


def main() -> int:
    data = json.loads(VENUES.read_text())
    venues = data["venues"]
    batch = build_batch_csv(venues)
    resp = post_batch(batch)
    matches = parse_results(resp)

    for i, v in enumerate(venues):
        lat, lon = matches.get(i, (None, None))
        v["lat"] = lat
        v["lon"] = lon

    VENUES.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    matched = sum(1 for v in venues if v.get("lat") is not None)
    print(f"Geocoded {matched}/{len(venues)} venues via Census batch.")
    unmatched = [v["name"] for v in venues if v.get("lat") is None]
    if unmatched:
        print("Unmatched:", unmatched)
    return 0


if __name__ == "__main__":
    sys.exit(main())
