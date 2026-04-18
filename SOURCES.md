# Data Sources & Methodology

How the Homegrown 2026 schedule and venue sidecar were assembled, which public sources were used, what worked, what didn't, and how to keep using these sources without getting rate-limited or banned.

Guiding principle: **feed-first, scrape-last**. Always try structured endpoints (REST, JSON, CSV, iCal, sitemap, open-data portals) before parsing HTML. Respect the operator's intent — identify yourself, throttle, cache, and don't hammer.

---

## 1. Schedule (`homegrown_2026_schedule.json`)

**Source:** `https://duluthhomegrown.org/schedule/`
**CMS:** WordPress 6.9.4 + Elementor, hosted on Flywheel.
**Scraper:** `scrape_schedule.py` (stdlib only).

### What we probed before scraping

| Endpoint | Result | Verdict |
|---|---|---|
| `/wp-json/wp/v2/posts` | 401 (Solid Security plugin) | REST API locked |
| `/wp-json/tribe/v1/events`, `/v2/events` | 404 | Events Calendar plugin not installed |
| `/feed/` | 200 (blog posts only) | No schedule entries |
| `/events/feed/ical/`, `/?feed=ical` | 404 | No iCal export |
| `robots.txt` sitemap | Empty urlset | No schedule URLs indexed |
| JSON-LD `<script type="application/ld+json">` | None present | No structured data |
| `__NEXT_DATA__` / `__NUXT__` / `__APOLLO_STATE__` | Absent | Plain PHP render |

Every upstream path returned 401, 404, empty, or blog-only content. The schedule exists only as DOM nodes in server-rendered HTML. **This is the scrape-justification memo** — don't skip it: if any of these ever start returning data (e.g. Homegrown installs The Events Calendar), switch to that source immediately.

### Scraping approach

Token-stream parser, not a selector tree. The stripped page text is a repeating sequence `[day header] → [time] → @ → [venue] → [act]`. Bounded to the by-time view by stopping at the second occurrence of the first day header (the page renders the schedule twice: by-time then by-venue).

Quirks handled:
- Zero-width spaces (`\u200b`) injected by Elementor — stripped before parsing (otherwise causes spurious diffs).
- An act occasionally has no preceding time in the HTML — it gets an empty `time_start` rather than inheriting the prior act's time.
- Script and style blocks stripped before tag removal (they contain `@` which would otherwise be mistaken for delimiters).

### Respectful use

- User-Agent identifies the scraper and includes a contact email.
- One GET per run. No JS rendering required; no headless browser.
- Designed for cron at human frequency (daily is plenty).
- Writes output atomically and diffs in-place — no need to re-fetch to inspect state.
- If the page structure changes materially, the parser errors loudly (`"No day headers found"`) rather than silently producing garbage. Re-check feeds first when that happens.

---

## 2. Venue core data (`homegrown_2026_venues.json` — address, website, etc.)

Compiled via general web search + targeted fetches. No single feed covers this.

**Primary sources, in order of trustworthiness:**

1. **Venue's own website** — authoritative for address, phone, hours, self-described capacity.
2. **Google Maps / Google Business Profile** — authoritative for current address and phone; less reliable for capacity or history.
3. **Wikipedia** — good for historic/landmark venues (Sacred Heart, West Theatre, Duluth Depot). Check cited sources, not article text.
4. **Local press archive**:
   - Duluth News Tribune (`duluthnewstribune.com`) — paywalled, but headlines/opening paragraphs usually readable.
   - Perfect Duluth Day (`perfectduluthday.com`) — excellent community blog, often has the opening date and backstory of venues.
   - Superior Telegram — Superior WI coverage.
5. **Visit Duluth** (`visitduluth.com`) — tourism site, address + short description.
6. **duluthhomegrown.org/venues/** — the festival's own per-venue pages.

### What to avoid

- Yelp/TripAdvisor descriptions written by reviewers — often wrong on founding years.
- AI-generated "business summary" blurbs in search result overview panels — these routinely fabricate capacity numbers. The Ursa Minor "55 standing" figure surfaced this way and was rejected because no primary source backed it.

---

## 3. Capacity (`capacity`, `capacity_source`)

Authoritative occupancy numbers aren't on the public web for most small venues. We triangulate in this order and **stop at the first hit per venue**:

| Tier | Source | Confidence tag | Notes |
|---|---|---|---|
| 1 | Posted fire-marshal occupant-load card, certificate of occupancy | `official` | Requires MDPA records request to Duluth Fire Marshal. Not currently filed. |
| 2 | City council agenda packet / liquor license application stating occupancy | `official` | Rare; found via Legistar PDF search. |
| 3 | Venue's own events/rental page ("holds up to X") | `venue-stated` | Found for Bent Paddle, Duluth Flame, Vikre, The Moorish Room. |
| 4 | Eventective / Peerspace / The Knot / WeddingSpot listing | `venue-stated` | Venue-provided to event platform. Found for All American Club, Wild State Cider. |
| 5 | Local press article quoting venue owner on capacity | `venue-stated` | Found for Norway Hall (DNT), West Theatre (PDD). |
| 6 | Parcel-record square footage ÷ IBC/IFC assembly ratio (7 sq ft standing / 15 sq ft tables) | `derived` | Last resort. None derived yet — St. Louis County parcel viewer is available but gives gross building area, not assembly-room area, which overstates capacity. |

**Discard rules:**
- Banquet-room-only figures (e.g. "Banquet Room 100+") aren't a total-venue capacity — leave null.
- Membership counts aren't occupancy (Owls Club "250 members" ≠ 250-person capacity).
- Pre-move or prior-operator capacities — don't carry forward across location or ownership changes.

### What we'd do next to fill the remaining 27 nulls

File a single Minnesota Data Practices Act request to the Duluth Fire Marshal listing all MN addresses, and a Wisconsin Public Records Law request to the Superior Fire Department for the WI addresses. Request: "current occupant load determination for the following assembly-use premises." Turnaround 1–2 weeks; sometimes a per-page copy fee. This is the only path to Tier 1 numbers for small bars.

---

## 4. Licenses (`licenses.business`, `licenses.liquor`)

Two jurisdictions, two very different discovery paths.

### City of Duluth, MN

**Working source:** `duluth-mn.legistar.com` — Granicus Legistar instance, Google-indexed, PDF agenda packets attached to City Clerk items.

**Useful queries:** Google site-restricted searches like
```
site:duluth-mn.legistar.com "on-sale" "annual"
site:duluth-mn.legistar.com filetype:pdf "license" 2025
```
The annual licensee list PDFs (attached to City Clerk agenda items) are the best single-document dump: legal entity, DBA, address, license class. License numbers and exact renewal dates are **not** published in these PDFs — renewal is annual via council approval; the packet date bounds the renewal year.

**Dead ends tried:**
- `opendata.duluthmn.gov` — does not exist (ECONNREFUSED).
- `webapi.legistar.com/v1/duluth/matters` — Legistar REST API not enabled for Duluth's tenant (returns a config error).
- Accela Citizen Access portal — requires a session and doesn't respond to unauthenticated API probes.
- `app.dps.mn.gov/AGEDIS5/` (MN DPS Alcohol & Gambling Enforcement) — CodeOnTime SPA, no public REST endpoints; would require browser automation for state-level brewer/distillery permits.

**Respectful use:** Legistar PDFs are large and cacheable — fetch once per council cycle, not per venue. Don't hit the Legistar search endpoint rapidly; use Google to find the PDF URL, then fetch the PDF directly from the `gateway.aspx?M=F&ID=...` or `View.ashx?...` link.

### City of Superior, WI

**Dead end:** the city's own license page at `superiorwi.gov/191/Licenses` is informational only, and Common Council agendas list license renewals in bulk ("miscellaneous licenses") without naming businesses.

**Working source:** **Wisconsin Department of Revenue retail alcohol beverage license search** — publicly exposes a REST endpoint that the official search page (`revenue.wi.gov/Pages/OnlineServices/Retail-Alcohol-Beverage-License-Search.aspx`) uses under the hood.

- Endpoint: `https://ww2.revenue.wi.gov/WebServicesPublicWeb/rest/liquor/all`
- Query params include `city`, `BB` (Class B Beer), `BL` (Class B Liquor), and others — discovered by reading the page's `LiqLic-Search.js`.
- Returns JSON with `entityName`, `businessName`, `address`, `expireDate`, `lastUpdated`, and boolean license-class flags.
- `expireDate` is the authoritative renewal horizon; subtract one year to get the last renewal date.

**Respectful use:** this is a public-facing API backing a web UI. Query by city, not per-address, to minimize request count — five Superior venues' data came back in one city-wide query (72 records). Cache locally; WI liquor licenses renew annually on July 1 for Class B, so one refresh per year plus one post-issuance refresh in late summer is sufficient.

### State-level fallbacks

- **MN Secretary of State business search** (`sos.state.mn.us/business-liens/business-filings/search/`) — for legal-entity lookup (active/inactive, filing dates, registered agent). Not a license record but useful to confirm a DBA's parent LLC.
- **WI DFI business search** (`wdfi.org`) — same role for Wisconsin entities.

### DBA-vs-legal-entity mismatches

The licensee on record is frequently an LLC that doesn't match the marquee name. Examples captured in the data: Carmody Irish Pub ← HIPPO DOWN THE STREET LLC, R.T. Quinlan's ← SILVER HAMMER INC, Kom-on-Inn ← JMM LLLP, Norway Hall ← WILD ROSE COMPANY LLC. When searching city records, try both the DBA and — if that fails — the address, which is the stable join key.

---

## 5. General respectful-use norms

These apply across every source above.

- **Always identify yourself.** A descriptive User-Agent with a contact email (or a URL explaining the project) turns a potential "block this bot" decision into "this is a named human, let them through."
- **Obey `robots.txt`.** Check it on first contact with a new host. Our schedule scrape confirmed `/schedule/` is not disallowed.
- **One request, then think.** Don't fan out. The schedule scraper makes one GET per run. The WI DOR enrichment made one city-wide query rather than 40 per-venue queries.
- **Cache locally.** PDFs especially — re-fetching a Legistar agenda packet on every run is wasteful and visible in the city's logs.
- **Run during off-hours** for municipal and small-business sites when possible. These are often on modest shared infrastructure.
- **Prefer the underlying JSON API over the user-facing HTML** when both exist (see WI DOR). It's cheaper for the operator and more reliable for you.
- **Never bypass authentication.** If an endpoint returns 401, that's a deliberate choice by the operator — stop there and find a different path. The WP REST API on duluthhomegrown.org returned 401 for good reason (Solid Security plugin); we didn't probe further.
- **Don't redistribute PII.** License records often include licensee home addresses for sole proprietors. Strip or aggregate before republishing.
- **Cite upstream.** Every record in `homegrown_2026_venues.json` includes a `sources` array and, for licenses, a direct `url` to the document. Future you (and anyone auditing the data) can verify without re-doing the research.

---

## 6. When a source goes dark

Expected failure modes and the response for each:

| Failure | Response |
|---|---|
| Schedule page HTML structure changes materially | Parser errors loudly. Re-probe `/wp-json/`, `/feed/`, sitemaps — Homegrown may have installed a plugin that exposes real feeds now. Prefer that path over rewriting the parser. |
| Legistar PDFs move or rename | Use site-restricted Google search on `duluth-mn.legistar.com` to rediscover. The `gateway.aspx?M=F&ID={GUID}` URL pattern is stable within a GUID; GUIDs regenerate per agenda item. |
| WI DOR REST endpoint changes path | Re-read the current version of `LiqLic-Search.js` on the public search page. The endpoint name has been stable for years but is not a contract. |
| City of Duluth stands up an open-data portal | Switch immediately — that would be the authoritative source and would eliminate the PDF parsing step. |
| Eventective / Peerspace remove a venue listing | Re-check the venue's own rental page; capacities often move between listing sites. |

---

## 7. Radio-play CSV matching (`the_north_plays.match_type`, `matched_as`)

**Source:** `the_local_plays.csv` — Spinitron export for WDSE 103.3 The North, covering spins from March 2025 through early 2026.

### Pass 1 — Exact and normalized matches (prior run)

16 acts matched with exact string equality against the CSV `artist` column; 1 matched after normalization (lowercasing, stripped punctuation, leading "The" dropped); 5 matched manually as fuzzy (see below).

### Pass 2 — Systematic fuzzy pass (this run)

All 163 remaining unmatched acts were evaluated against all 365 unique CSV artists using two independent similarity metrics:

1. **`difflib.SequenceMatcher.ratio()`** on fully normalized strings (lowercase, ASCII-folded accents, stripped punctuation, collapsed whitespace, leading "The " dropped).
2. **Token-set Jaccard** (each string treated as a bag of tokens; `|A ∩ B| / |A ∪ B|`).

Acceptance thresholds:
- SequenceMatcher ratio ≥ 0.88, OR
- One normalized string fully contains the other AND the contained string is ≥ 6 chars, OR
- Token-set Jaccard ≥ 0.75 AND both strings have ≥ 2 tokens, OR
- All tokens of the shorter name appear in the longer name (substring-token rule).

False-positive guards: single-token matches with ratio < 0.92 rejected; different lead tokens with ratio < 0.80 and no containment rejected.

**Result: 0 new matches found.** The highest ratio across all 163 × 365 comparisons was 0.75 (Lu Starr ↔ Plumstar — clearly different artists). A containment hit (Four Mile Portage ∋ "Portage") was inspected and rejected as a false positive (Portage is a separate CSV artist).

Conclusion: the 22 existing matches are complete. The remaining 163 unmatched acts are genuinely absent from The North's 2025–2026 airplay record, not missed by the matching algorithm.

---

## 8. Social media discovery (YouTube, Instagram)

**Fields added:** `youtube` and `instagram` on each act object. Schema:

```json
"youtube": { "url": "...", "handle": "@handle or null", "confidence": "high|medium|low", "note": "optional" } | null
"instagram": { "url": "...", "handle": "handle without @", "confidence": "high|medium|low", "note": "optional" } | null
```

### Discovery method (stop at first hit per platform per act)

1. **Act's own website / Bandcamp** — fetched for all acts where a dedicated website was discoverable (e.g. `skarlettwoods.com`, `grandhollerband.com`, `breannemarie.com`, `grantgladmusic.com`, `cyrandthecosmonauts.com`, `roryvanjames.org`, `leeclarkallen.com`, etc.). Website footer links are authoritative — the artist put them there.
2. **Google/DuckDuckGo site-restricted search** — queries of the form `"<act name>" Duluth Minnesota instagram youtube` and `site:instagram.com "<act name>"`. Returned direct Instagram profile URLs in search snippets for the majority of acts.
3. **Bandcamp social links** — Bandcamp artist pages list social links in the sidebar (`ironrangeoutlawbrigade.bandcamp.com` → YouTube `@Kjenaas218`; `therealhalfsleeper.bandcamp.com` → YouTube channel + Instagram).
4. **Duluth Homegrown festival pages** (`duluthhomegrown.org/bands/<slug>/`) — these pages do not expose artist social links; they only contain a bio and festival sponsor links. Not a productive source.
5. **One profile verification fetch per act** where the URL was obtained from a search snippet rather than the act's own site, to confirm the account exists and is the right act.

### Confidence rules applied

- `high` — URL sourced from artist's own website, or Bandcamp sidebar, or the handle clearly matches the act name AND the account bio/posts reference Duluth/MN/Superior/Twin Cities.
- `medium` — handle matches name, account is active, plausible geography, but no explicit local signal (e.g. `rick_e_mick` for Rick McLean Band; `duluth_dolls` where two competing handles exist).
- `null` — no findable account (Slape, Sugar on the Roof, Life Parade, Father Hennepin, Venus de Mars and All The Pretty Horses, Janie and The Spokes, Sons of Fogtown, Witchfarm, and many others). Many hyperlocal bar bands have no public social media; null is the honest answer.

### Rate-limit and block events

None encountered. All fetches were single-page GETs to public profile pages. The Instagram profile pages fetched returned public content without challenge. Observed several-second gaps between requests. No platform served a CAPTCHA or rate-limit response during this run.

### Summary of social data added (2026-04-15 run)

| Metric | Count |
|---|---|
| Acts with YouTube added | 16 (15 high, 1 medium) |
| Acts with Instagram added | 40 (38 high, 2 medium) |
| Acts where both YouTube and Instagram found | 10 |
| Acts searched but left null (no findable account) | ~145 |

Representative high-confidence finds: Skarlett Woods (`@skarlettwoods` YT + `skarlett_woods` IG — from artist website), Grand Holler (channel ID + `grandholler` IG — from band website), Cyr and the Cosmonauts (`@cyrandthecosmonauts` both — from band website), Steve Solkela (`@stevesolkela` both — Wikipedia + Instagram snippet).

Acts intentionally left null despite searching:
- **Slape** — Facebook presence only; no Instagram or YouTube found.
- **Sugar on the Roof** — Bandcamp and Facebook only; no Instagram found (no public Instagram indexed for this roots quartet).
- **Life Parade** — Facebook and Bandcamp only; no Instagram or YouTube found.
- **Father Hennepin** — Facebook page only; no band-specific Instagram or YouTube.
- **Venus de Mars and All The Pretty Horses** — Minneapolis-based, Facebook and Bandcamp, no Instagram or YouTube channel found.
- **Janie and The Spokes** — Facebook and Bandcamp only.
- **Sons of Fogtown** — no findable Instagram or YouTube.
- **Witchfarm** — too common as a search term; no band-specific Instagram found.
- **Polari** — extremely common name (Olly Alexander album, various labels); no Duluth-specific account distinguishable.

---

_Last updated: 2026-04-15._
