#!/usr/bin/env python3
"""
Find a YouTube video for each Homegrown act by searching YouTube and parsing
the ytInitialData JSON blob from the search results page (no JS rendering needed).
"""
import json, re, time, sys, urllib.request, urllib.parse
from pathlib import Path

ACTS_FILE = Path("homegrown_2026_acts.json")
CACHE_DIR = Path("/tmp/homegrown-yt-cache")
CACHE_DIR.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def search_youtube(query):
    cache = CACHE_DIR / (re.sub(r'\W+', '_', query)[:80] + ".html")
    if cache.exists():
        html = cache.read_text(errors="replace")
    else:
        url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query})
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            cache.write_text(html)
            time.sleep(2.5)
        except Exception as e:
            print(f"  FETCH ERROR: {e}")
            return []
    # Extract ytInitialData JSON
    m = re.search(r'var ytInitialData\s*=\s*(\{.*?\});\s*</script>', html, re.DOTALL)
    if not m:
        m = re.search(r'ytInitialData"\s*>\s*(\{.*?\})\s*</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    # Walk the JSON to find video renderers
    videos = []
    def walk(obj):
        if isinstance(obj, dict):
            if "videoRenderer" in obj:
                vr = obj["videoRenderer"]
                vid = vr.get("videoId", "")
                title = ""
                if "title" in vr and "runs" in vr["title"]:
                    title = "".join(r.get("text", "") for r in vr["title"]["runs"])
                if vid:
                    videos.append({"videoId": vid, "title": title})
            else:
                for v in obj.values():
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(data)
    return videos

def score_match(act_name, video_title):
    an = act_name.lower().strip()
    vt = video_title.lower()
    if an in vt:
        return 3
    # Drop "the " prefix
    an2 = re.sub(r'^the\s+', '', an)
    if an2 in vt:
        return 2
    # Token overlap
    act_tokens = set(re.findall(r'\w+', an))
    vid_tokens = set(re.findall(r'\w+', vt))
    overlap = len(act_tokens & vid_tokens) / max(len(act_tokens), 1)
    if overlap >= 0.6:
        return 1
    return 0

def main():
    data = json.loads(ACTS_FILE.read_text())
    acts = data["acts"]
    updated = 0
    skipped = 0
    # Non-musical act keywords
    skip_kw = ["kickball", "merch fair", "proclamation", "dance project", "resource center"]

    for i, act in enumerate(acts):
        name = act["name"]
        # Skip if already has a high-confidence video
        yv = act.get("youtube_video", {}) or {}
        if yv.get("url") and yv.get("confidence") == "high":
            continue
        # Skip non-musical entries
        if any(kw in name.lower() for kw in skip_kw):
            act["youtube_video"] = {"url": None, "title": None, "confidence": None, "note": "non-musical act"}
            skipped += 1
            continue

        print(f"[{i+1}/{len(acts)}] {name}...", end=" ", flush=True)

        # Try multiple search queries
        queries = [
            f'"{name}" music',
            f'"{name}" duluth minnesota',
            f'{name} band live',
        ]
        best_video = None
        best_score = 0
        for q in queries:
            results = search_youtube(q)
            for v in results[:5]:
                s = score_match(name, v["title"])
                # Duluth/MN/Homegrown in title = bonus
                vt = v["title"].lower()
                if any(w in vt for w in ["duluth", "minnesota", "homegrown", "mn"]):
                    s += 1
                if s > best_score:
                    best_score = s
                    best_video = v
            if best_score >= 3:
                break

        if best_video and best_score >= 1:
            conf = "high" if best_score >= 3 else ("medium" if best_score >= 2 else "low")
            url = f"https://www.youtube.com/watch?v={best_video['videoId']}"
            act["youtube_video"] = {
                "url": url,
                "title": best_video["title"],
                "confidence": conf,
                "note": None
            }
            updated += 1
            print(f"✓ [{conf}] {best_video['title'][:60]}")
        else:
            if not yv.get("url"):
                act["youtube_video"] = {"url": None, "title": None, "confidence": None, "note": "no match found"}
            print("✗ no match")

    ACTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"\nDone. Updated: {updated}, Skipped: {skipped}, Total: {len(acts)}")

if __name__ == "__main__":
    main()
