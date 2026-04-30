#!/usr/bin/env python3
"""
Apply targeted social-link fixes to homegrown_2026_acts.json.

Each fix is keyed by act name, and only patches the specific field. Operations:

  REPLACE_FIELD(act, field, new_value)        -- set field = new_value
  CLEAR_FIELD(act, field)                     -- set field = null
  REPLACE_NESTED_URL(act, field, new_url)     -- for {url, ...} objects, replace .url
                                                 (and add a note documenting why)
  DROP_OBJECT_FIELD(act, field, reason)       -- set field = null with rationale

Run after validate_social_links.py confirms each problem.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PATH = Path(__file__).with_name("homegrown_2026_acts.json")


def replace_field(act, field, new_value):
    act[field] = new_value


def clear_field(act, field):
    act[field] = None


def replace_nested_url(act, field, new_url, new_note=None, new_title=None):
    obj = act.get(field)
    if not isinstance(obj, dict):
        raise SystemExit(f"  ! {act['name']}: {field} is not an object")
    obj["url"] = new_url
    if new_note is not None:
        obj["note"] = new_note
    if new_title is not None:
        obj["title"] = new_title


# Ordered list of (act_name, op, *args, comment_for_log)
PATCHES = [
    # ---- YouTube video replacements ----
    ("Horse Fzce", "replace_nested_url", "youtube_video",
     "https://www.youtube.com/watch?v=nOH4lHyORsI",
     "Replaced dead video Rpf1PWBMjUc with band's official 'Tales We Could Tell' video.",
     "swap dead YT video for working official",
     "Horse Fzce - Tales We Could Tell (Official Video)"),

    ("The Repairmen", "replace_nested_url", "youtube_video",
     "https://www.youtube.com/watch?v=oXCkqyYyQvQ",
     "Replaced dead video Ykan6mFtLdI with The Repairmen Band 3-24/4-2-26 performance.",
     "swap dead YT video for live performance",
     "The Repairmen 3-24 / 4-2-26"),

    # ---- YouTube channel URL format change ----
    ("Iron Range Outlaw Brigade", "replace_nested_url", "youtube",
     "https://www.youtube.com/user/Kjenaas218",
     "Channel still active under /user/Kjenaas218 (handle URL @Kjenaas218 returns 404).",
     "switch to /user/ form (handle 404s)",
     None),

    # ---- Apple Music: drop wrong-artist link for The Jambronies ----
    ("The Jambronies", "clear_field", "apple_music",
     None, None,
     "Apple Music page shows 'The Jambrones' (different / older act); existing record's note already flagged this as uncertain."),

    # ---- Websites ----
    ("DJ Nola", "replace_field", "website",
     "https://djnolacom.wordpress.com/",
     None,
     "djnola.com is a frameset that loads djnolacom.wordpress.com; link directly to the WP site."),

    ("P.B&J", "clear_field", "website",
     None, None,
     "thepbjband.com domain no longer resolves (NXDOMAIN)."),

    ("Pronoya", "clear_field", "website",
     None, None,
     "pronoyamn.com domain no longer resolves (NXDOMAIN); band has bandcamp + IG."),

    ("Slape", "clear_field", "website",
     None, None,
     "slapemusic.com NXDOMAIN; slape.com is a domain-parking page (not the band)."),

    ("Stel", "clear_field", "website",
     None, None,
     "stelmusic.com domain no longer resolves; band has bandcamp."),

    ("The Shane Nelson Band", "replace_field", "website",
     "https://www.twinportsrocks.com/shane-nelson-music",
     None,
     "shanenelsonmusic.com TLS handshake fails; old http URL redirects to twinportsrocks.com which serves the band's page."),

    ("Venus de Mars and All The Pretty Horses", "clear_field", "website",
     None, None,
     "venusdemars.com is a DreamHost 'site not found' parking page (https has self-signed cert)."),

    # ---- Facebook ----
    ("Ashe Berton", "replace_field", "facebook",
     "https://www.facebook.com/p/Ashe-Berton-Music-61576720794488/",
     None,
     "Old URL (ashley.berton/) was a personal profile (login wall); new URL is the band page."),

    ("Grant Glad & the Soo Line Loons", "clear_field", "facebook",
     None, None,
     "facebook.com/SooLineLoons/ no longer renders content (page deleted or never owned by band); search finds no current FB page."),

    ("Peat Boggs", "clear_field", "facebook",
     None, None,
     "facebook.com/peatboggs/ no longer renders content; band's primary social is IG (@peatboggs)."),

    ("Stel", "clear_field", "facebook",
     None, None,
     "facebook.com/musicstel/ no longer renders content; no current band FB page found."),

    # NOTE: Underground 'til Sundown, BOOG3YM3N, Bellerpuss, Israel Malachi
    # Orchestra all have FB URLs flagged as 'missing' by the validator, but
    # web-search confirms the pages still exist — they are gated behind FB's
    # login wall for anonymous users. URLs left as-is.
]


def main():
    data = json.loads(PATH.read_text())
    acts = data["acts"]
    by_name = {a["name"]: a for a in acts}

    for entry in PATCHES:
        name, op = entry[0], entry[1]
        act = by_name.get(name)
        if act is None:
            print(f"  ! act not found: {name}", file=sys.stderr)
            continue
        if op == "replace_field":
            field = entry[2]
            new_value = entry[3]
            note = entry[4]
            comment = entry[5]
            old = act.get(field)
            replace_field(act, field, new_value)
            print(f"  {name}: {field}: {old!r} -> {new_value!r}  [{comment}]")
        elif op == "clear_field":
            field = entry[2]
            note = entry[4]
            comment = entry[5]
            old = act.get(field)
            clear_field(act, field)
            print(f"  {name}: {field}: {old!r} -> None  [{comment}]")
        elif op == "replace_nested_url":
            field = entry[2]
            new_url = entry[3]
            new_note = entry[4]
            comment = entry[5]
            new_title = entry[6] if len(entry) > 6 else None
            obj = act.get(field)
            old_url = obj.get("url") if isinstance(obj, dict) else None
            replace_nested_url(act, field, new_url, new_note=new_note, new_title=new_title)
            print(f"  {name}: {field}.url: {old_url!r} -> {new_url!r}  [{comment}]")
        else:
            print(f"  ! unknown op: {op}", file=sys.stderr)

    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nWrote {PATH}")


if __name__ == "__main__":
    main()
