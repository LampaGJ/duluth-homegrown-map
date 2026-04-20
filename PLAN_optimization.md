# Optimization Review Plan

## Goal
Thorough code review of index.html (~3100 lines) for performance, memory, and power optimization — especially on mobile devices.

## Areas to Review

### 1. Three.js / WebGL
- [ ] **Geometry budget**: Count total triangles (terrain grid is HM_W×HM_H = 1024×660 = 675K vertices). Consider reducing on mobile.
- [ ] **Draw calls**: Each venue has cubes + flag + rings + rope = many objects. Consider instanced meshes for cubes (same geometry, different color/position).
- [ ] **Texture memory**: Heightmap PNG (1024×660), diffuse map canvas, flag canvas textures (one per venue = 40 textures). Consider texture atlas for flags.
- [ ] **Shader complexity**: onBeforeCompile patches add warp, slope blend, vinyl grooves, disc crop. Profile GPU time.
- [ ] **Preload iframes**: YT_PRELOAD_COUNT hidden iframes waste memory. Consider reducing or removing on mobile.
- [ ] **Animation loop**: tick() runs every frame with flag wave, ring rotation, rope updates for all 40 venues. Consider frustum culling or LOD.
- [ ] **Renderer pixel ratio**: Capped at 3 — consider 2 on mobile to halve pixel count.
- [ ] **Dispose unused**: When switching between YT/BC/SP embeds, old iframes pile up. Ensure cleanup.

### 2. DOM / CSS
- [ ] **Single file**: Everything in one 3100-line HTML file. Consider splitting CSS into separate file for caching.
- [ ] **Font loading**: 5 Google Fonts + Material Icons + opentype.js Permanent Marker. Audit which are actually used on mobile.
- [ ] **Unused CSS**: Desktop-only styles still parsed on mobile. Consider media query splitting.
- [ ] **Fixed positioning stack**: Multiple fixed elements on mobile (setlist, scrubber, schedule, sky-bg, sky-overlay, yt-wrap). Minimize repaints.
- [ ] **Tooltip DOM**: Tooltip innerHTML rebuilt on every pointermove. Consider reuse/pooling.

### 3. JavaScript
- [ ] **D3.js usage**: Only using d3.group, d3.timeFormat, d3.min/max. Consider dropping D3 for these trivial operations.
- [ ] **fitty.js**: Check if still used. Remove if not.
- [ ] **Schedule data**: Both schedule JSON and acts JSON loaded. Combined they're ~500KB. Consider merged/minified data.
- [ ] **Event listeners**: Multiple pointermove handlers on canvas. Consolidate.
- [ ] **setInterval for YT scrub**: 500ms polling loop. Use requestAnimationFrame or YT API events instead.
- [ ] **localStorage**: Multiple reads/writes on every interaction. Batch.

### 4. Network / Loading
- [ ] **Image sizes**: duluth_skyline_med.jpg (285KB), duluth_heightmap.png (185KB), topojson (112KB). Total ~600KB before JS.
- [ ] **Three.js bundle**: Loading from CDN via importmap. Verify tree-shaking or switch to smaller build.
- [ ] **Lazy load**: Defer opentype.js, D3, YouTube API until needed.
- [ ] **Service worker**: Consider for offline capability at the festival (no cell service in some venues).

### 5. Mobile-Specific
- [ ] **Touch handling**: OrbitControls captures all touch events. Ensure schedule scrolling isn't blocked.
- [ ] **Memory pressure**: iPhone Safari limits WebGL memory. Monitor for context loss.
- [ ] **Battery**: Continuous animation loop drains battery. Consider pausing when tab hidden or user idle.
- [ ] **Viewport units**: Multiple `calc()` with vh units. iOS Safari dynamic vh issues.
- [ ] **Safe area**: iPhone notch/dynamic island. Check with `env(safe-area-inset-top)`.

## Execution
1. Profile on real iPhone (Safari) + Android (Chrome) using remote debugging
2. Run Lighthouse audit (performance, accessibility, best practices)
3. Fix critical issues first (memory leaks, excessive draw calls)
4. Then optimize load time (lazy loading, code splitting)
5. Finally polish (reduce repaints, battery optimization)
