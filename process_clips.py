#!/usr/bin/env python3
"""
Download YouTube audio, detect chorus via pychorus, extract clips.
Run from the project venv: .venv/bin/python process_clips.py
"""
import json, os, re, subprocess, sys

ACTS_FILE = "homegrown_2026_acts.json"
AUDIO_DIR = "/tmp/homegrown-audio"
CLIPS_DIR = "clips"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

from pychorus import find_and_output_chorus

def sanitize(s):
    return re.sub(r'[<>:"/\\|?*]', '', s).strip()[:80]

def main():
    with open(ACTS_FILE) as f:
        data = json.load(f)

    processed = 0
    skipped = 0

    for act in data["acts"]:
        if act.get("type") != "band_set":
            continue
        yv = act.get("youtube_video") or {}
        url = yv.get("url", "")
        if not url:
            continue

        m = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not m:
            continue
        vid_id = m.group(1)
        audio_path = os.path.join(AUDIO_DIR, f"{vid_id}.mp3")

        # Download if needed
        if not os.path.exists(audio_path):
            print(f"  Downloading {act['name']}...")
            ytdlp = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
            result = subprocess.run([
                ytdlp,
                "-x", "--audio-format", "mp3", "--audio-quality", "5",
                "--download-sections", "*0:00-5:00",
                "--sleep-interval", "2",
                "-o", os.path.join(AUDIO_DIR, f"{vid_id}.%(ext)s"),
                url
            ], capture_output=True, text=True)
            # yt-dlp might save with different extension then convert
            for ext in [".mp3", ".m4a", ".webm", ".opus"]:
                candidate = os.path.join(AUDIO_DIR, f"{vid_id}{ext}")
                if os.path.exists(candidate) and ext != ".mp3":
                    subprocess.run(["ffmpeg", "-y", "-i", candidate, "-q:a", "5", audio_path],
                                   capture_output=True)
                    break

        if not os.path.exists(audio_path):
            print(f"  SKIP {act['name']} — download failed")
            skipped += 1
            continue

        artist = sanitize(act["name"])
        song_title = sanitize(yv.get("title", "Unknown"))

        # Skip if clip already exists for this act (prevent duplicates)
        existing = [f for f in os.listdir(CLIPS_DIR) if f.startswith(artist + " - ")]
        if existing:
            print(f"already have clip, skipping")
            continue

        # Use pychorus to find the chorus
        print(f"  Analyzing {act['name']}...", end=" ", flush=True)
        clip_wav = os.path.join(CLIPS_DIR, f"_temp_{vid_id}.wav")

        try:
            chorus_start = find_and_output_chorus(audio_path, clip_wav, clip_length=15)
        except Exception as e:
            print(f"pychorus failed ({e}), defaulting to 30s")
            chorus_start = 30.0

        if chorus_start is None:
            print("no chorus found, defaulting to 30s")
            chorus_start = 30.0

        # Format timestamp
        mins = int(chorus_start) // 60
        secs = int(chorus_start) % 60
        ts = f"{mins:02d}:{secs:02d}"

        # Extract final clip as MP3 with 3-sec padding
        clip_name = f"{artist} - {song_title} - {ts}.mp3"
        clip_path = os.path.join(CLIPS_DIR, clip_name)

        pad_start = max(0, chorus_start - 3)
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(pad_start), "-t", "21",  # 3 before + 15 chorus + 3 after
            "-c:a", "libmp3lame", "-q:a", "5",
            clip_path
        ], capture_output=True)

        # Clean up temp wav
        if os.path.exists(clip_wav):
            os.remove(clip_wav)

        act["refrain_start"] = round(chorus_start, 1)
        act["refrain_end"] = round(chorus_start + 15, 1)
        act["clip_file"] = f"clips/{clip_name}"

        print(f"chorus at {ts}")
        processed += 1

    with open(ACTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone. Processed: {processed}, Skipped: {skipped}")

if __name__ == "__main__":
    main()
