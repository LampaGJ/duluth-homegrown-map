#!/usr/bin/env python3
"""
Re-analyze downloaded audio to find the actual chorus/refrain.
Better algorithm: find the most REPEATED section with high energy,
preferring the middle of the song over the ending.

Overwrites clip files and updates acts JSON.
"""
import json, os, glob, re, subprocess
import numpy as np

ACTS_FILE = "homegrown_2026_acts.json"
AUDIO_DIR = "/tmp/homegrown-audio"
CLIPS_DIR = "clips"

try:
    import librosa
except ImportError:
    print("Installing librosa...")
    subprocess.run(["pip3", "install", "librosa", "numpy"], check=True)
    import librosa

os.makedirs(CLIPS_DIR, exist_ok=True)

def find_chorus(filepath, max_duration=300):
    """Find the chorus using repetition detection + energy weighting."""
    y, sr = librosa.load(filepath, duration=max_duration, sr=22050)
    duration = len(y) / sr

    # Compute chroma features (pitch content)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)

    # Compute RMS energy
    rms = librosa.feature.rms(y=y, hop_length=512)[0]

    # Segment the song into ~8-12 sections
    n_segments = min(12, max(6, int(duration / 15)))
    try:
        bounds = librosa.segment.agglomerative(chroma, k=n_segments)
    except Exception:
        bounds = np.linspace(0, chroma.shape[1], n_segments + 1, dtype=int)

    bound_times = librosa.frames_to_time(bounds, sr=sr, hop_length=512)

    # For each segment, compute:
    # 1. How similar it is to OTHER segments (repetition score)
    # 2. Its average energy
    # 3. Position penalty (prefer middle, penalize last 15%)
    segments = []
    seg_chromas = []

    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        if e - s < 3:  # skip tiny segments
            continue
        seg_chroma = chroma[:, s:e]
        seg_chromas.append(np.mean(seg_chroma, axis=1))  # average chroma vector

        avg_energy = np.mean(rms[s:e]) if e <= len(rms) else np.mean(rms[s:])
        t_start = bound_times[i] if i < len(bound_times) else 0
        t_end = bound_times[i + 1] if i + 1 < len(bound_times) else duration

        # Position score: 1.0 in middle, drops at start and end
        mid_frac = (t_start + t_end) / 2 / duration
        if mid_frac > 0.85:
            pos_score = 0.3  # heavily penalize endings
        elif mid_frac < 0.15:
            pos_score = 0.6  # slightly penalize intros
        else:
            pos_score = 1.0

        segments.append({
            'start': t_start,
            'end': t_end,
            'energy': avg_energy,
            'pos_score': pos_score,
            'idx': len(seg_chromas) - 1
        })

    if not segments or not seg_chromas:
        return duration * 0.3, duration * 0.3 + 15  # fallback: 30% in

    # Compute repetition score: how similar each segment is to other segments
    seg_vecs = np.array(seg_chromas)
    for seg in segments:
        vec = seg_vecs[seg['idx']]
        sims = np.dot(seg_vecs, vec) / (np.linalg.norm(seg_vecs, axis=1) * np.linalg.norm(vec) + 1e-8)
        # Repetition = number of other segments with high similarity
        seg['repetition'] = np.sum(sims > 0.85) - 1  # subtract self

    # Normalize energy
    max_energy = max(s['energy'] for s in segments) or 1

    # Combined score: repetition * energy * position
    for seg in segments:
        seg['score'] = (
            seg['repetition'] * 2.0 +          # repeated sections score high
            (seg['energy'] / max_energy) * 1.5 + # loud sections score high
            seg['pos_score'] * 1.0               # middle sections preferred
        )

    # Pick the best
    segments.sort(key=lambda s: -s['score'])
    best = segments[0]

    return best['start'], best['end']


def extract_clip(input_path, start, end, output_path):
    """Extract clip with 3-sec padding, using ffmpeg."""
    pad_start = max(0, start - 3)
    pad_end = end + 3
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-ss", str(pad_start), "-to", str(pad_end),
        "-c:a", "libmp3lame", "-q:a", "5",
        output_path
    ], capture_output=True)


def sanitize(s):
    return re.sub(r'[<>:"/\\|?*]', '', s).strip()[:80]


def main():
    with open(ACTS_FILE) as f:
        data = json.load(f)

    # Find all downloaded audio files
    audio_files = {}
    for f in glob.glob(os.path.join(AUDIO_DIR, "*.mp3")):
        vid_id = os.path.splitext(os.path.basename(f))[0]
        audio_files[vid_id] = f

    processed = 0
    for act in data["acts"]:
        if act.get("type") != "band_set":
            continue
        yv = act.get("youtube_video") or {}
        url = yv.get("url", "")
        if not url:
            continue

        # Extract video ID
        m = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not m:
            continue
        vid_id = m.group(1)

        audio_path = audio_files.get(vid_id)
        if not audio_path or not os.path.exists(audio_path):
            # Try to download if not already done
            audio_path = os.path.join(AUDIO_DIR, f"{vid_id}.mp3")
            if not os.path.exists(audio_path):
                print(f"  Downloading {act['name']}...")
                result = subprocess.run([
                    "yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "5",
                    "--download-sections", "*0:00-5:00",
                    "-o", audio_path.replace(".mp3", ".%(ext)s"),
                    url
                ], capture_output=True, text=True)
                # yt-dlp might save with different extension
                for ext in [".mp3", ".m4a", ".webm", ".opus"]:
                    candidate = audio_path.replace(".mp3", ext)
                    if os.path.exists(candidate):
                        audio_path = candidate
                        break

        if not os.path.exists(audio_path):
            print(f"  SKIP {act['name']} — no audio file")
            continue

        print(f"  Analyzing {act['name']}...", end=" ", flush=True)

        try:
            refrain_start, refrain_end = find_chorus(audio_path)
        except Exception as e:
            print(f"FAIL ({e})")
            refrain_start = 30
            refrain_end = 45

        # Format timestamp
        mins = int(refrain_start) // 60
        secs = int(refrain_start) % 60
        ts = f"{mins:02d}:{secs:02d}"

        song_title = sanitize(yv.get("title", "Unknown"))
        artist = sanitize(act["name"])
        clip_name = f"{artist} - {song_title} - {ts}.mp3"
        clip_path = os.path.join(CLIPS_DIR, clip_name)

        extract_clip(audio_path, refrain_start, refrain_end, clip_path)

        act["refrain_start"] = round(refrain_start, 1)
        act["refrain_end"] = round(refrain_end, 1)
        act["clip_file"] = f"clips/{clip_name}"

        print(f"chorus at {ts} ({refrain_end - refrain_start:.0f}s)")
        processed += 1

    with open(ACTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone. Processed {processed} acts.")


if __name__ == "__main__":
    main()
