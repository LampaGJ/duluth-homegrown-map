# YouTube Mini-Player Feature Plan

## Concept
A small YouTube embed that auto-plays each band's video in festival chronological order (ties broken alphabetically). The player sits above the timeline scrubber and tracks the chrome slider knob position.

## Behavior

### Positioning
1. **Start**: player anchored at far-left of timeline, never going off-screen
2. **Phase 1** (playhead before player center): player stays at left edge; playhead moves toward it
3. **Phase 2** (playhead reaches player center): player begins moving rightward in unison with playhead + chrome knob
4. **Phase 3** (playhead near right edge): player stops at far-right edge; playhead continues to end

### Playback
- Each act's `youtube_video.url` (176/185 now populated) feeds a YouTube iframe embed
- Videos play in festival chronological order: sorted by `(date, time_start_24h, act_name_alpha)`
- When the timeline scrubber advances past an act's time window, the player loads the next video
- Manual scrubbing jumps to the corresponding act's video
- Muted by default with visible unmute button

### Implementation

```
<div id="yt-player-wrap">
  <div id="yt-player-label">Now: {act name} @ {venue}</div>
  <iframe id="yt-player" src="..." allow="autoplay" />
</div>
```

CSS:
- `position: absolute` within the scrubber area, above the equalizer
- `bottom: 100%` of scrubber + small gap
- `left` computed per-frame from slider value (clamped to [0, scrubberWidth - playerWidth])
- Width: ~280px, height: ~160px (16:9)
- Semi-transparent border, backdrop-blur, rounded corners (match scrubber style)

JS:
- Build sorted playlist from `sortedSets` joined with `acts[].youtube_video.url`
- On slider input / playback tick: find current act, if changed → update iframe src
- Use YouTube IFrame API for autoplay + mute control
- `playerLeft = Math.max(0, Math.min(thumbX - playerW/2, scrubberW - playerW))`

### Data Requirements
- 176/185 acts have `youtube_video.url` — 9 without get skipped in the playlist
- Playlist order: pre-sorted array of `{time, act, venue, videoUrl}`

### Edge Cases
- Acts with null youtube_video: skip in playlist, show "No video available" card
- Multiple simultaneous acts: pick the one alphabetically first
- Iframe load time: show a loading spinner overlay until video starts
- Mobile: stack below scrubber instead of above; smaller embed (240×135)
