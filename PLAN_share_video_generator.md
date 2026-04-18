# Share Video Generator — Implementation Plan

## Architecture

```
User clicks "Generate Video" in share dialog
  → Shadow DOM host created off-screen (1080×1920)
  → 2D Canvas inside shadow root
  → GSAP timeline animates the set list onto the canvas
  → canvas.captureStream(30) + MediaRecorder → WebM blob
  → Progress bar in the UI
  → Download link + share options
  → Shadow DOM host removed
```

## Animation Storyboard (10 seconds, 30fps)

### Scene 1: Title (0–2s)
- Notebook paper background fades in
- User's emoji appears center-top (bounce in)
- Set list title scribbles in letter-by-letter (Caveat font, handwriting effect)
- Hand-drawn red underline sweeps across

### Scene 2: Day-by-day acts (2–8s)
- Each day header slides in with its day color
- Acts write themselves in one-by-one with time + venue
- Subtle ruled-line background scrolls up as content grows
- Each act has a brief highlight glow as it appears

### Scene 3: Festival branding (8–10s)
- "HOMEGROWN 2026" fades in (Bebas Neue, large)
- Duluth skyline photo peeks through the knockout text
- "duluthhomegrown.org" + dates fade in below
- Festival day-color gradient bar at bottom

## Output Formats (from video_specs.json)

| Platform | Resolution | Aspect | Duration |
|---|---|---|---|
| TikTok | 1080×1920 | 9:16 | ≤3min |
| IG Reels | 1080×1920 | 9:16 | ≤90s |
| IG Stories | 1080×1920 | 9:16 | ≤60s |
| YouTube Shorts | 1080×1920 | 9:16 | ≤60s |
| Bluesky | 1080×1920 | 9:16 | ≤60s |
| Facebook Reels | 1080×1920 | 9:16 | ≤90s |

All platforms converge on 1080×1920 9:16. Render once, export once.

## Technical Details

### Canvas Rendering
- Load Caveat + Bebas Neue fonts via FontFace API (ensure loaded before rendering)
- Draw notebook ruled lines as repeating pattern
- Text rendering: fillText with Caveat, letter-by-letter for scribble effect
- Day colors from DAY_COLORS palette

### GSAP Timeline
```js
const tl = gsap.timeline();
tl.to(titleProxy, { progress: 1, duration: 1.5, onUpdate: drawTitle });
tl.to(dayProxy, { progress: 1, duration: 5, onUpdate: drawActs });
tl.to(brandProxy, { progress: 1, duration: 1.5, onUpdate: drawBranding });
```

### MediaRecorder
```js
const stream = canvas.captureStream(30);
const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
recorder.ondataavailable = (e) => chunks.push(e.data);
recorder.onstop = () => { blob = new Blob(chunks); download(blob); };
```

### Shadow DOM
```js
const host = document.createElement('div');
host.style.cssText = 'position:fixed;left:-9999px;width:1080px;height:1920px;';
document.body.appendChild(host);
const shadow = host.attachShadow({ mode: 'closed' });
const canvas = document.createElement('canvas');
canvas.width = 1080; canvas.height = 1920;
shadow.appendChild(canvas);
```

## Dependencies
- GSAP (CDN): `https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js`
- No other deps — pure canvas 2D rendering

## Edge Cases
- Empty set list → show "No acts starred yet" message
- Very long set list (>30 acts) → increase animation duration proportionally
- Font loading failure → fallback to sans-serif
- MediaRecorder not supported → fallback to animated GIF via gif.js
