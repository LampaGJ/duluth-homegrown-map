#!/usr/bin/env python3
"""
Scrape the Duluth Homegrown Music Festival schedule and emit JSON.

Output structure:
    {
      "festival": "...",
      "source": {...},
      "extracted_at": "...",
      "record_count": N,
      "changes": {
          "compared_to": "<previous file path or null>",
          "added":   [ {date, time_start, venue, act}, ... ],
          "removed": [ ... ],
          "moved":   [ {act, from: {...}, to: {...}}, ... ]
      },
      "schedule": [ ... ]
    }

Usage:
    python3 scrape_schedule.py [--out OUT.json] [--prev PREV.json]

Defaults:
    --out  homegrown_2026_schedule.json
    --prev same as --out  (diff against the previous run in place)

Run via cron, e.g. daily at 07:00:
    0 7 * * * cd /Users/graham/Projects/homegrown && /usr/bin/python3 scrape_schedule.py >> scrape.log 2>&1
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://duluthhomegrown.org/schedule/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

DAY_HEADER_RE = re.compile(r"^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}(am|pm)$", re.IGNORECASE)

MONTHS = {m: i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip_to_lines(raw: str) -> list[str]:
    raw = re.sub(r"<script\b[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", raw)
    text = html.unescape(text)
    # Strip zero-width and other invisible whitespace that WordPress/Elementor
    # sometimes injects — left in, they cause spurious adds/removes across runs.
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def infer_year(day_label: str, now: dt.date) -> int:
    # Festival runs late April / early May. Roll year forward once this year's
    # festival has passed so the scraper continues to target the next edition.
    mon_abbr = day_label.split()[1]
    month = MONTHS[mon_abbr]
    day = int(day_label.split()[2])
    year = now.year
    candidate = dt.date(year, month, day)
    if candidate < now - dt.timedelta(days=30):
        year += 1
    return year


def to_24h(t: str) -> str:
    m = re.match(r"^(\d{1,2}):(\d{2})(am|pm)$", t, re.IGNORECASE)
    if not m:
        return ""
    hh, mm, mer = int(m.group(1)), m.group(2), m.group(3).lower()
    if mer == "am":
        hh = 0 if hh == 12 else hh
    else:
        hh = 12 if hh == 12 else hh + 12
    return f"{hh:02d}:{mm}"


def parse(lines: list[str], today: dt.date) -> list[dict]:
    # Schedule repeats twice on the page (by-time, then by-venue). Bound to
    # the first copy: everything from the first day header up to the second
    # occurrence of that same header.
    day_positions = [i for i, l in enumerate(lines) if DAY_HEADER_RE.match(l)]
    if not day_positions:
        raise RuntimeError("No day headers found — page structure may have changed.")
    first_label = lines[day_positions[0]]
    repeat_idx = next(
        (i for i in day_positions[1:] if lines[i] == first_label),
        len(lines),
    )
    seg = lines[day_positions[0]:repeat_idx]

    records: list[dict] = []
    current_day_label = None
    current_date = None
    current_time = None  # carries forward: adjacent acts at one venue/time omit the repeated time label

    i = 0
    while i < len(seg):
        tok = seg[i]
        if DAY_HEADER_RE.match(tok):
            current_day_label = tok
            year = infer_year(tok, today)
            mon = MONTHS[tok.split()[1]]
            day = int(tok.split()[2])
            current_date = dt.date(year, mon, day)
            current_time = None
            i += 1
            continue
        if TIME_RE.match(tok):
            current_time = tok.lower()
            i += 1
            continue
        if tok == "@" and i + 2 < len(seg):
            venue = seg[i + 1]
            act = seg[i + 2]
            if current_date is None:
                i += 3
                continue
            records.append({
                "date": current_date.isoformat(),
                "day_of_week": current_day_label.split()[0],
                "day_label": current_day_label,
                "time_start": current_time or "",
                "time_start_24h": to_24h(current_time) if current_time else "",
                "venue": venue,
                "act": act,
            })
            i += 3
            continue
        i += 1

    return records


def diff(prev: list[dict], curr: list[dict]) -> dict:
    def key(r):  # act identity across runs
        return (r["act"].lower().strip(), r["date"])

    def slot(r):
        return (r["date"], r["time_start_24h"], r["venue"])

    prev_map = {key(r): r for r in prev}
    curr_map = {key(r): r for r in curr}

    added = [curr_map[k] for k in curr_map.keys() - prev_map.keys()]
    removed = [prev_map[k] for k in prev_map.keys() - curr_map.keys()]
    moved = []
    for k in curr_map.keys() & prev_map.keys():
        if slot(prev_map[k]) != slot(curr_map[k]):
            moved.append({
                "act": curr_map[k]["act"],
                "from": {"date": prev_map[k]["date"], "time_start": prev_map[k]["time_start"], "venue": prev_map[k]["venue"]},
                "to":   {"date": curr_map[k]["date"], "time_start": curr_map[k]["time_start"], "venue": curr_map[k]["venue"]},
            })

    added.sort(key=lambda r: (r["date"], r["time_start_24h"], r["venue"]))
    removed.sort(key=lambda r: (r["date"], r["time_start_24h"], r["venue"]))
    moved.sort(key=lambda m: (m["to"]["date"], m["act"]))

    return {"added": added, "removed": removed, "moved": moved}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="homegrown_2026_schedule.json")
    ap.add_argument("--prev", default=None, help="Previous JSON to diff against (defaults to --out)")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--html", default=None, help="Use local HTML file instead of fetching")
    args = ap.parse_args()

    out_path = Path(args.out)
    prev_path = Path(args.prev) if args.prev else out_path

    raw = Path(args.html).read_text() if args.html else fetch(args.url)
    lines = strip_to_lines(raw)
    today = dt.date.today()
    records = parse(lines, today)

    prev_records: list[dict] = []
    prev_file = None
    if prev_path.exists():
        try:
            prev_data = json.loads(prev_path.read_text())
            prev_records = prev_data.get("schedule", [])
            prev_file = str(prev_path)
        except json.JSONDecodeError:
            prev_file = None

    changes = {
        "compared_to": prev_file,
        **diff(prev_records, records),
    }
    changes["summary"] = {
        "added": len(changes["added"]),
        "removed": len(changes["removed"]),
        "moved": len(changes["moved"]),
    }

    output = {
        "festival": "Duluth Homegrown Music Festival",
        "source": {
            "url": args.url,
            "cms": "WordPress + Elementor (server-rendered HTML)",
            "extraction_method": "HTML scrape: day-header / time / @ / venue / act token stream, bounded to by-time view",
        },
        "extracted_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "record_count": len(records),
        "changes": changes,
        "schedule": records,
    }

    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    s = changes["summary"]
    print(f"[{output['extracted_at']}] {len(records)} records → {out_path}  "
          f"(added {s['added']}, removed {s['removed']}, moved {s['moved']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
