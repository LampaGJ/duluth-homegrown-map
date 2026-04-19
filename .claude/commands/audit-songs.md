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
- "Halfsleeper" → Chelsea Wolfe song
- "Hypochondriac" → Sasha Alex Sloan song

**How to detect:** If the video title contains an artist name that is NOT the act name, or the title matches a famous song unrelated to the band, flag it.

### 2. Generic name → playlist/compilation/competition match
Band names that are common English words often match playlists, compilations, or unrelated competitions.
- "Old Love" → "Old Love Songs - Playlist"
- "Homegrown Tomatoes" → Guy Clark/John Denver cover
- "Sometime, Maybe" → "Lucas Bokman Wong - Sometime Maybe | 2025 Global Music Competition" (band name was the SONG title, not the artist)

**How to detect:** Title contains words like "Playlist", "Compilation", "Mix", "Top 10", "Best of", "Competition", "Contest". Also flag when the band name appears as a song/album title performed by a DIFFERENT artist in the video title.

### 3. Product/brand/event match
The video is about a product, event, or brand that shares the band's name.
- "Dirt Magnet" → Finegear Dirt Magnet (synthesizer module, Superbooth demo)
- "Witchfarm" → "WitchFarm V2 Bugfix Proof" (software)
- "Slape" → "Slape - Sound Effect" (sound effect clip)

**How to detect:** Title contains product-related words: "review", "demo", "unboxing", "tutorial", "NAMM", "Superbooth", "specs", "bugfix", "sound effect", brand names unrelated to music.

### 4. Wrong genre/language signals
The video is clearly from a genre/scene/language incompatible with a Duluth indie/punk/folk act:
- K-pop, J-pop, anime OST (e.g., Crimson Soul → Kuro Kiryu anime)
- Bollywood
- Video game soundtracks (e.g., Mid Dream → Bleach Rebirth Of Souls OST)
- Movie soundtracks
- Classical/orchestral (unless the act is actually orchestral)
- German-language pop (e.g., Bratwurst → German music video)
- Santhali/non-English music (e.g., porb → Santhali language song)
- French-language music from non-Duluth artists

**How to detect:** Non-English titles, anime/game/film references, genre tags in title that don't match local indie scene.

### 5. Title doesn't reference the band at all
If the video title contains zero words from the band name AND the `sourceType` is not "band_channel", it's likely wrong. Especially suspect if `sourceType` is "venue" or "search".
- "Entheos Enclave" → video titled '"One Reason" at the Caddyshack' (actually Indecent Proposal's video, not Entheos Enclave)
- "Lu Starr" → video titled "Duluth Dylan Fest 2025 Songwriter Contest" (generic event, no mention of Lu Starr)

**How to detect:** Strip common words (the, and, a, of, in, at, for, &) from band name. If NO remaining words appear in the video title, flag it. Verify by checking if the video URL/channel actually belongs to the band.

### 6. Confidence + sourceType cross-check
- `sourceType: "venue"` videos are often wrong — they're from venue channels that uploaded random footage, or the video is of a DIFFERENT band at that venue
- `confidence: "low"` entries are the most suspect — prioritize auditing these
- `confidence: "high"` does NOT mean correct — the search algorithm is naive and frequently over-confident on generic names
- Videos with very high view counts (millions) for an unknown local band are almost certainly wrong-artist matches

### 7. Apple Music / Bandcamp ID cross-check
Check the `sources` array and platform links for wrong-artist matches too:
- Apple Music: "Dirty Sound Magnet" for "Dirt Magnet", "Kidzone" for "Owls Club Big Band", "Brenda K Starr" for "Lu Starr"
- Bandcamp: witchfarm.bandcamp.com was a UK artist, not the Duluth band
- Spotify: check that the Spotify artist is actually from Duluth/MN

**How to detect:** If the Apple Music/Bandcamp/Spotify artist name doesn't match the act name, or the artist is clearly from a different city/country, flag it.

### 8. No Duluth/Minnesota connection
Every act at Homegrown is from the Duluth/Superior/Iron Range area or has strong Minnesota ties. If a web search for `"<band name>" duluth` or `"<band name>" minnesota` returns zero relevant results, the matched video/artist is almost certainly a different act with the same name from somewhere else entirely. This is the strongest disqualifier — a band playing Homegrown WILL have some Minnesota footprint (local press, venue listings, Bandcamp location, social media mentioning Duluth).
- "Baharat" → Batov Records EP (UK world music label, not the Duluth band)
- "Galleon" → European dance act "One Sign"
- "Stel" → Sophia Stel (Vancouver alt-pop, not the Duluth artist)
- "WICKIE" → German children's show theme song
- "Sometime, Maybe" → Lucas Bokman Wong (Vancouver/Yale classical pianist)

**How to detect:** Search `"<band name>" duluth band` or `"<band name>" minnesota music`. If the only results are for an artist from another city/country with no MN connection, flag it.

### 9. Video belongs to a DIFFERENT band at same venue
A video filmed at a Duluth venue may show a completely different band, not the one we're looking for. The URL or uploader domain may reveal whose video it actually is.
- "Entheos Enclave" → video was from indyp218.com (Indecent Proposal's website), filmed at Caddyshack but showing Indecent Proposal, not Entheos Enclave

**How to detect:** Check if the video URL, uploader channel, or description references a different band. If the title mentions a website or channel that belongs to another act, flag it.

## Procedure

1. Read `homegrown_2026_acts.json`
2. For each act with `type: "band_set"` and a non-null `youtube_video`:
   - Apply all 9 detection rules above
   - Prioritize checking `confidence: "low"` and `sourceType: "venue"` entries first
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

Also check and null wrong `apple_music`, `bandcamp`, or `spotify` entries if they belong to a different artist (see Rule 7).

## Sanitization

After any edits, sanitize the JSON:
- Replace curly/smart quotes (`\u201c \u201d \u2018 \u2019`) with straight quotes in all string values
- Strip zero-width characters (`\u200b \u200c \u200d \ufeff`)
- Validate: `python3 -c "import json; json.load(open('homegrown_2026_acts.json'))"`
- Rewrite via `json.dump(data, f, indent=2, ensure_ascii=False)` to normalize
