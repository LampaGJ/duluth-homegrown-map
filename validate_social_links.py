#!/usr/bin/env python3
"""
Validate every outbound social/streaming URL in homegrown_2026_acts.json.

For each act, probes spotify, apple_music, bandcamp, instagram, facebook,
website, youtube, youtube_video. Detects:

  - hard 4xx / 5xx
  - soft 404s on Instagram ("Page not found") and Facebook (login wall on
    a vanity URL = unknown — flagged INFO)
  - Apple Music artist page where the artist name doesn't match the act
  - YouTube video unavailable (oEmbed 401/404)
  - Spotify artist page where the title doesn't match the act
  - Bandcamp 404 + subdomain not-found

Writes a JSON report to social_link_audit.json with one entry per act.
Concurrency keeps wall time manageable (~2 min for 185 acts).

stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path

ACTS_PATH = Path(__file__).with_name("homegrown_2026_acts.json")
OUT_PATH = Path(__file__).with_name("social_link_audit.json")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)
TIMEOUT = 15
MAX_WORKERS = 12


def normalize(s: str) -> str:
    """Loose comparison key — strip punctuation, lower, collapse whitespace.
    & == and, accents stripped to closest ASCII."""
    s = unescape(s or "")
    # Map common name-equivalent tokens before stripping punctuation.
    s = s.replace("&", " and ")
    s = re.sub(r"[^A-Za-z0-9]+", "", s).lower()
    # 'the' is often dropped/added; treat as optional.
    if s.startswith("the"):
        s = s[3:]
    return s


def fetch(url: str, method: str = "GET", max_redirects: int = 5):
    """Returns (status, final_url, body_text_or_none, error_str_or_none)."""
    if not url:
        return (None, None, None, "empty url")
    seen = 0
    current = url
    while True:
        req = urllib.request.Request(
            current,
            method=method,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
                # Decode best-effort.
                ctype = resp.headers.get("Content-Type", "")
                charset = "utf-8"
                m = re.search(r"charset=([\w-]+)", ctype)
                if m:
                    charset = m.group(1)
                try:
                    text = body.decode(charset, errors="replace")
                except LookupError:
                    text = body.decode("utf-8", errors="replace")
                return (resp.status, resp.geturl(), text, None)
        except urllib.error.HTTPError as e:
            # Manual redirect handling for 3xx that urlopen didn't follow.
            if e.code in (301, 302, 303, 307, 308) and seen < max_redirects:
                loc = e.headers.get("Location")
                if loc:
                    current = urllib.parse.urljoin(current, loc)
                    seen += 1
                    continue
            return (e.code, current, None, f"HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e:
            return (None, current, None, f"URLError {e.reason}")
        except Exception as e:  # timeouts, ssl, etc.
            return (None, current, None, f"{type(e).__name__}: {e}")


# -------- per-platform validators --------

def check_instagram(url: str, _act_name: str):
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    # Instagram returns 200 with "Sorry, this page isn't available." for missing handles.
    if text and "Sorry, this page isn't available" in text:
        return ("missing", "Instagram: account not found", final)
    if text and "Page Not Found" in text and "Instagram" in text:
        return ("missing", "Instagram: page not found", final)
    if status == 200:
        return ("ok", None, final)
    return ("error", f"status {status}", final)


def check_facebook(url: str, _act_name: str):
    """Facebook serves real og:title content to crawlers ONLY on the new
    /p/{Slug-NumericID}/ page format. Vanity URLs like /BandName/ return a
    generic <title>Facebook</title> with no og:title to anonymous crawlers
    whether the page exists or not, so we can't tell login-wall from deleted.

    Strategy:
      - If 4xx/5xx: error.
      - If og:title is set: definitely a real page (ok).
      - Else (generic 'Facebook' title, no og:title): we cannot prove it's
        broken from anonymous probes; flag as 'gated' (informational), not
        'missing' — a logged-in user can usually still reach it.
    """
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    if status != 200 or not text:
        return ("error", f"status {status}", final)
    og = re.search(r'<meta property="og:title" content="([^"]+)"', text)
    if og and og.group(1).strip().lower() != "facebook":
        return ("ok", None, final)
    return ("gated", "Facebook: anonymous probe sees login wall — page may exist, may not", final)


def check_spotify(url: str, act_name: str):
    """The regular open.spotify.com page is a JS app — <title> renders empty
    server-side. Spotify's oEmbed endpoint returns JSON with the real artist
    name, so use that for identity verification."""
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    if status != 200:
        return ("error", f"status {status}", final)
    # Identity check via oEmbed.
    oembed_url = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(url, safe="")
    os_, _of, otext, oerr = fetch(oembed_url)
    if oerr or os_ != 200 or not otext:
        return ("ok", None, final)
    try:
        meta = json.loads(otext)
    except Exception:
        return ("ok", None, final)
    page_name = meta.get("title")
    if page_name and normalize(act_name):
        n_page = normalize(page_name)
        n_act = normalize(act_name)
        if n_page != n_act and n_act not in n_page and n_page not in n_act:
            return ("mismatch", f"Spotify shows '{page_name}', expected '{act_name}'", final)
    return ("ok", None, final)


def check_apple_music(url: str, act_name: str):
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    if status != 200:
        return ("error", f"status {status}", final)
    # Apple's <title> looks like: ‎Artist Name - Apple Music
    m = re.search(r"<title>[‎]*\s*([^<]+?)\s*-\s*Apple Music\s*</title>", text or "")
    page_name = m.group(1) if m else None
    if page_name and normalize(act_name) and normalize(page_name) != normalize(act_name):
        if normalize(act_name) not in normalize(page_name) and normalize(page_name) not in normalize(act_name):
            return ("mismatch", f"Apple Music shows '{page_name}', expected '{act_name}'", final)
    return ("ok", None, final)


def check_bandcamp(url: str, _act_name: str):
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    if status == 404:
        return ("missing", "Bandcamp 404", final)
    if text and "<h2>Sorry, that something isn" in text:
        return ("missing", "Bandcamp: page not found", final)
    if status == 200:
        return ("ok", None, final)
    return ("error", f"status {status}", final)


def check_youtube_video(url: str, _act_name: str):
    """oEmbed returns 401/404 for unavailable/private videos."""
    if not url:
        return ("ok", None, url)
    oembed = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe="")
    status, final, text, err = fetch(oembed)
    if status == 200:
        return ("ok", None, url)
    if status in (401, 404):
        return ("missing", f"YouTube video unavailable (oembed {status})", url)
    if err:
        return ("error", err, url)
    return ("error", f"oembed status {status}", url)


def check_youtube_channel(url: str, _act_name: str):
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    if status != 200:
        return ("error", f"status {status}", final)
    if text and "This channel does not exist" in text:
        return ("missing", "YouTube: channel not found", final)
    return ("ok", None, final)


def check_generic(url: str, _act_name: str):
    """Plain website / unknown — only HTTP-level checks."""
    status, final, text, err = fetch(url)
    if err:
        return ("error", err, final)
    if status and 200 <= status < 400:
        return ("ok", None, final)
    return ("error", f"status {status}", final)


def url_of(v):
    if not v:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("url")
    return None


PLATFORMS = [
    # field name, label, url-extractor, checker
    ("spotify", "spotify", url_of, check_spotify),
    ("apple_music", "apple_music", url_of, check_apple_music),
    ("bandcamp", "bandcamp", url_of, check_bandcamp),
    ("instagram", "instagram", url_of, check_instagram),
    ("facebook", "facebook", url_of, check_facebook),
    ("website", "website", url_of, check_generic),
    ("youtube", "youtube", url_of, check_youtube_channel),
    ("youtube_video", "youtube_video", url_of, check_youtube_video),
]


def audit_act(act):
    name = act.get("name", "")
    findings = []
    for field, label, getter, checker in PLATFORMS:
        url = getter(act.get(field))
        if not url:
            continue
        verdict, note, final_url = checker(url, name)
        findings.append(
            {
                "platform": label,
                "url": url,
                "final_url": final_url,
                "verdict": verdict,
                "note": note,
            }
        )
    return {"act": name, "findings": findings}


def main():
    data = json.loads(ACTS_PATH.read_text())
    acts = data["acts"]
    print(f"Auditing {len(acts)} acts...", file=sys.stderr)

    results = [None] * len(acts)
    started = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(audit_act, a): i for i, a in enumerate(acts)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:
                results[i] = {"act": acts[i].get("name", "?"), "findings": [{"verdict": "error", "note": f"audit crash: {e}"}]}
            completed += 1
            if completed % 10 == 0 or completed == len(acts):
                elapsed = time.time() - started
                print(f"  {completed}/{len(acts)} ({elapsed:.1f}s)", file=sys.stderr)

    # Aggregate stats.
    stats = {"ok": 0, "missing": 0, "mismatch": 0, "error": 0, "gated": 0}
    for r in results:
        for f in r["findings"]:
            stats[f["verdict"]] = stats.get(f["verdict"], 0) + 1

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stats": stats,
        "results": results,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_PATH}", file=sys.stderr)
    print(
        f"  ok={stats['ok']}  missing={stats['missing']}  mismatch={stats['mismatch']}  "
        f"error={stats['error']}  gated={stats.get('gated', 0)}",
        file=sys.stderr,
    )

    # Print problems summary (gated entries listed separately as info).
    print("\n--- problems ---", file=sys.stderr)
    for r in results:
        bad = [f for f in r["findings"] if f["verdict"] in ("missing", "mismatch", "error")]
        if bad:
            print(f"\n{r['act']}", file=sys.stderr)
            for f in bad:
                print(f"  [{f['verdict']:8}] {f['platform']:14} {f['note']}  ->  {f['url']}", file=sys.stderr)


if __name__ == "__main__":
    main()
