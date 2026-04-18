---
allowed-tools: [Read, Grep, Glob, Bash, Agent, WebSearch, WebFetch]
description: "Audit youtube_video entries in acts JSON for wrong-artist matches"
---

# /audit-songs — Detect False Song Matches

Scan `homegrown_2026_acts.json` for YouTube videos that don't actually belong to the Duluth Homegrown band. These are local/indie acts — any match to a famous artist, product, or unrelated content is wrong.

## Detection Rules

Apply every rule below to each act with a non-null `youtube_video`. Flag any match.

### 1. Famous song/artist collision
The video title or channel matches a well-known artist, not the local band. Examples caught previously:
- "Southpaw" → Eminem movie soundtrack
- "Chasm" → Genshin Impact game OST
- "WILBUR" → Wilbur Soot (YouTuber/musician)
- "Boxcar" → Boxcar Willie (country singer)
- "Polari" → Olly Alexander (Years & Years)
- "Born too Late" → Poni-Tails (1950s doo-wop)
- "Kroma" → SAINT JHN remix
- "Nevins" → Run DMC
- "Theory of Light" → Eternal Eclipse

**How to detect:** If the video title contains an artist name that is NOT the act name, or the title matches a famous song unrelated to the band, flag it.

### 2. Generic name → playlist/compilation match
Band names that are common English words often match playlists or compilations instead of the actual band.
- "Old Love" → "Old Love Songs - Playlist"
- "Homegrown Tomatoes" → Guy Clark/John Denver cover

**How to detect:** Title contains words like "Playlist", "Compilation", "Mix", "Top 10", "Best of", or the title is just the band name repeated (likely a cover of a famous song with that title).

### 3. Product/brand/event match
The video is about a product, event, or brand that shares the band's name.
- "Dirt Magnet" → Finegear Dirt Magnet (synthesizer module, Superbooth demo)

**How to detect:** Title contains product-related words: "review", "demo", "unboxing", "tutorial", "NAMM", "Superbooth", "specs", brand names unrelated to music.

### 4. Wrong genre signals
The video is clearly from a genre/scene incompatible with a Duluth indie/punk/folk act:
- EDM/trap remix channels
- K-pop or J-pop
- Bollywood
- Video game soundtracks (title mentions game names)
- Movie soundtracks (title mentions film names)
- Classical/orchestral (unless the act is actually orchestral)

### 5. Title doesn't reference the band at all
If the video title contains zero words from the band name AND the `sourceType` is not "band_channel", it's likely wrong. Especially suspect if `sourceType` is "venue" or "search".

### 6. Confidence + sourceType cross-check
- `sourceType: "venue"` videos are often wrong — they're from venue channels that uploaded random footage
- `confidence: "high"` does NOT mean correct — the search algorithm is naive and frequently over-confident on generic names
- Videos with very high view counts (millions) for an unknown local band are almost certainly wrong-artist matches

### 8. No Duluth/Minnesota connection
Every act at Homegrown is from the Duluth/Superior/Iron Range area or has strong Minnesota ties. If a web search for `"<band name>" duluth` or `"<band name>" minnesota` returns zero relevant results, the matched video/artist is almost certainly a different act with the same name from somewhere else entirely. This is the strongest disqualifier — a band playing Homegrown WILL have some Minnesota footprint (local press, venue listings, Bandcamp location, social media mentioning Duluth).

**How to detect:** Search `"<band name>" duluth band` or `"<band name>" minnesota music`. If the only results are for an artist from LA/NYC/Nashville/etc. with no MN connection, flag it.

### 7. Apple Music ID cross-check
Check the `sources` array too. If it contains an Apple Music URL for a different artist (e.g., "Dirty Sound Magnet" for "Dirt Magnet", "Kidzone" for "Owls Club Big Band"), flag the Apple Music entry as wrong.

## Procedure

1. Read `homegrown_2026_acts.json`
2. For each act with `type: "band_set"` and a non-null `youtube_video`:
   - Apply all 8 detection rules above
   - For ambiguous cases, do a quick web search: `"<band name>" duluth band` to confirm whether the band exists and whether the video matches
3. Report findings as a table: `| Act | Video Title | Rule Violated | Recommendation |`
4. Ask the user before making any changes to the JSON

## What to null out when fixing

When a wrong match is confirmed, set these fields to `null`:
- `youtube_video`
- `refrain_start`
- `refrain_end`  
- `clip_file`

Do NOT remove other valid fields (bandcamp, spotify, instagram, etc.).
