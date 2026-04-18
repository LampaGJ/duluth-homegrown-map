# Mobile Optimization Issues

## Performance

### Issue 1: Terrain mesh segment count too high for mobile GPUs
- Current: 768×495 = 380K quads
- Target: detect mobile via `navigator.maxTouchPoints > 0` and drop to 256×165 (42K quads)
- Also reduce basemap canvas to 2048×1320 (from 4096×2640)

### Issue 2: Per-frame vertex updates on 40 flag meshes
- Each flag: 20 segments × 2 rows = ~40 vertices updated per frame
- 40 flags × 40 verts = 1600 vertex updates/frame
- On mobile: reduce to 10 segments per flag, or skip wave animation for distant flags

### Issue 3: Three.js pixel ratio
- Currently `min(devicePixelRatio, 3)` — on iPhone 15 Pro that's 3× = 9× pixel count
- Mobile target: cap at 2

### Issue 4: 4096×2640 basemap canvas texture
- 43MB uncompressed in GPU memory
- Mobile: use 1024×660 (the DEM resolution)

## UX

### Issue 5: Touch interaction conflicts
- OrbitControls touch: pinch-zoom vs browser zoom
- Scrubber slider: touch drag needs larger hit area (44px min tap target)
- Flag hover tooltips: no hover on touch — need tap-to-show / tap-away-to-dismiss

### Issue 6: Layout
- Panel below map (done in CSS media query)
- Scrubber fixed at bottom (done)
- Tweak panel: auto-hide on mobile (F2 to show)
- Day labels: truncate to "Sun 4/26" (done)

### Issue 7: Orientation
- Landscape mode on phones: map fills width, scrubber stays visible
- Portrait: map at 45vh (done), schedule below

## Geolocation Features

### Issue 8: "What's my nearest venue?"
- Use `navigator.geolocation.getCurrentPosition()` to get user lat/lon
- Compute haversine distance to each venue
- Sort venues by distance, highlight nearest on map
- Show a "Nearest: {venue name} — {distance}" badge

### Issue 9: Google Maps directions links
- Each venue tooltip and schedule row: add "Get Directions" link
- URL format: `https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&destination_place_id={name}`
- Or simpler: `https://maps.google.com/?q={lat},{lon}`
- On iOS: detect and use `maps://` scheme for Apple Maps

### Issue 10: Venue proximity notifications
- If geolocation is active and user is within 200m of a venue, show a "You're at {venue}!" badge
- List currently playing acts at that venue
- Link to the venue's full schedule

## Implementation Priority
1. Issue 3 (pixel ratio cap) — quick win, big perf gain
2. Issue 1 (terrain LOD) — moderate effort, big perf gain
3. Issue 4 (texture size) — tied to Issue 1
4. Issue 5 (touch interactions) — UX critical
5. Issue 9 (Google Maps links) — high user value, easy
6. Issue 8 (nearest venue) — high user value, moderate
7. Issue 2 (flag LOD) — nice to have
8. Issue 10 (proximity) — nice to have
