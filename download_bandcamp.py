#!/usr/bin/env python3
"""Download audio from Bandcamp for acts that failed YouTube download."""
import json, os, re, subprocess, sys

ACTS_FILE = "homegrown_2026_acts.json"
AUDIO_DIR = "/tmp/homegrown-audio"
YTDLP = os.path.join(os.path.dirname(sys.executable), "yt-dlp")

with open(ACTS_FILE) as f:
    data = json.load(f)

# Acts with Bandcamp but no clip yet
for act in data["acts"]:
    if act.get("clip_file") or act.get("type") != "band_set":
        continue
    bc = act.get("bandcamp")
    if not bc:
        continue

    name = act["name"]
    # Create a safe filename from act name
    safe = re.sub(r'[<>:"/\\|?*]', '', name).strip()[:40]
    out_path = os.path.join(AUDIO_DIR, f"bc_{safe}.mp3")

    if os.path.exists(out_path):
        print(f"  SKIP {name} — already downloaded from Bandcamp")
        continue

    print(f"  Downloading {name} from Bandcamp: {bc}")
    result = subprocess.run([
        YTDLP, "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "--playlist-items", "1",  # just the first/top track
        "-o", out_path.replace(".mp3", ".%(ext)s"),
        bc
    ], capture_output=True, text=True, timeout=120)

    if result.returncode == 0:
        # Find the actual output file
        for ext in [".mp3", ".m4a", ".opus", ".webm"]:
            candidate = out_path.replace(".mp3", ext)
            if os.path.exists(candidate):
                if ext != ".mp3":
                    subprocess.run(["ffmpeg", "-y", "-i", candidate, "-q:a", "5", out_path], capture_output=True)
                print(f"    OK — saved as {out_path}")
                break
    else:
        print(f"    FAIL — {result.stderr[:100]}")

print("Done")
