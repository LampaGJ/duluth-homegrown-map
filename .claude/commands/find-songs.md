---
allowed-tools: [Read, Grep, Glob, Bash, Agent, WebSearch, WebFetch]
description: "Find correct YouTube videos for acts missing them in the acts JSON"
---

# /find-songs — Find Correct YouTube Videos for Homegrown Acts

Find verified YouTube videos for Duluth Homegrown Music Festival acts that are missing `youtube_video` in `homegrown_2026_acts.json`.

## Search Strategy

For each act missing a video, execute searches in this priority order. Stop at the first confirmed match.

### Tier 1: Direct band presence
1. Search YouTube: `"<band name>" duluth`
2. Search YouTube: `"<band name>" homegrown`
3. Search YouTube: `"<band name>" minnesota`
4. Check if the act has a YouTube channel URL in the `youtube` field — visit it for uploadable content

### Tier 2: Cross-reference from known links
5. Check the act's `bandcamp` URL — Bandcamp pages often link to YouTube or list member names
6. Check the act's `instagram` handle — bio may link to YouTube
7. Check the act's `facebook` URL — may have video posts or YouTube links
8. Check the act's `website` — may embed YouTube videos
9. If member names are discoverable, search: `"<member name>" duluth music`

### Tier 3: Venue and media coverage
10. Search: `"<band name>" site:youtube.com "duluth"` or `"<band name>" site:youtube.com "homegrown"`
11. Search for TCS (Twin Cities Sessions) or KTWH or PBS Backroads features: `"<band name>" TCS` or `"<band name>" KTWH`
12. Search: `"<band name>" "duluth songwriter showcase"`
13. Search: `"<band name>" site:youtube.com` + known Duluth venue names (Sir Benedict's, Caddyshack, Pizza Luce, Wussow's, Red Herring, Carmody, 218 Taphouse)

### Tier 4: Alternate names
14. Check if the act has aliases (e.g., "Homegrown Tomatoes" → "Salt and Pine"). Cross-reference social media handles that differ from the band name.
15. Search YouTube for any alternate/prior band name + duluth

## Verification Checklist

A video MUST pass ALL of these checks before being set:

- [ ] **Duluth/MN connection confirmed**: Video title, description, or channel mentions Duluth, Superior, MN, Minnesota, Iron Range, Twin Ports, North Shore, or a known Duluth venue
- [ ] **Band name matches**: The act name (or confirmed alias) appears in the video title, description, or channel name
- [ ] **It's actually music**: Not a product demo, sound effect, tutorial, gameplay, reaction video, or unrelated content
- [ ] **Correct genre plausibility**: The music style is plausible for a Duluth indie/punk/folk/rock/hip-hop/electronic act (not K-pop, Bollywood, major label pop, orchestral film score, etc.)
- [ ] **Not a cover BY a famous artist**: If the title contains a famous artist name (Eminem, Chelsea Wolfe, Run DMC, etc.), it's wrong unless the famous artist is covering the local band (extremely unlikely)
- [ ] **Not a playlist/compilation**: Title does not contain "Playlist", "Compilation", "Mix", "Top 10", "Best of"
- [ ] **View count sanity**: A video with millions of views for an unknown local band is almost certainly a different artist

## What to set

For each verified match, update the act in `homegrown_2026_acts.json`:

```json
"youtube_video": {
  "url": "https://www.youtube.com/watch?v=<id>",
  "title": "<exact video title>",
  "confidence": "high",
  "note": null,
  "sourceType": "<type>"
}
```

sourceType values:
- `"band"` — uploaded by the band's own channel
- `"band_channel"` — from the band's official YouTube channel
- `"fan"` — filmed by audience member at a show
- `"venue"` — uploaded by a venue's channel
- `"media"` — from a media outlet (TCS, KTWH, PBS, newspaper)
- `"label"` — from a record label channel

## Procedure

1. Read `homegrown_2026_acts.json`
2. Collect all acts with `type: "band_set"` and null `youtube_video`
3. For each, run through the search tiers above
4. Apply the verification checklist to every candidate
5. Report findings as: `| Act | URL | Title | sourceType | Verification Notes |`
6. Update the JSON for confirmed matches
7. List acts that remain unfound

## Important

- **Never guess.** If uncertain, leave null. Run `/audit-songs` afterward to double-check.
- **Prefer live performance videos** over lyric videos or visualizers — they prove the band exists and performs in the area.
- **Prefer recent videos** over old ones when multiple are available.
- **One video per act** — pick the best quality / most representative one.
- **Dispatch parallel subagents** if there are many acts to search — split into batches of 8-10.
- **Sanitize all text before writing to JSON.** Replace curly/smart quotes (`\u201c \u201d \u2018 \u2019`) with straight quotes. Strip zero-width characters (`\u200b \u200c \u200d \ufeff`). After writing, always validate the JSON parses: `python3 -c "import json; json.load(open('homegrown_2026_acts.json'))"`. Rewrite via `json.dump()` to normalize encoding.
