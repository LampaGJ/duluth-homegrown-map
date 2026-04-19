#!/usr/bin/env python3
"""Add genre_category field to homegrown_2026_acts.json"""
import json, re

CATEGORY_RULES = [
    # Order matters: more specific patterns first
    # Electronic/DJ
    (r'\b(edm|electro|techno|dubstep|house|dance music|electronica|bass music)\b', 'Electronic/DJ'),
    # Hip-Hop/Rap
    (r'\b(hip-hop|hip hop|rap)\b', 'Hip-Hop/Rap'),
    # Jazz
    (r'\b(big band jazz|jazz fusion|jazz-rock fusion|gypsy jazz)\b', 'Jazz'),
    (r'^jazz$', 'Jazz'),
    # Blues
    (r'^blues[- ]rock$', 'Blues'),
    (r'^blues\b', 'Blues'),
    # Folk/Americana
    (r'\b(folk|americana|country|bluegrass|acoustic|singer-songwriter|honky-tonk|appalachian|fiddle|celtic|old-time|western swing|shanty|maritime|outlaw country)\b', 'Folk/Americana'),
    # Funk/Soul/R&B
    (r'\b(funk|soul|r&b|neo-soul|gospel)\b', 'Funk/Soul/R&B'),
    # Punk (check before rock)
    (r'\b(punk|hardcore|crust|post-hardcore|metalcore|mathcore)\b', 'Punk'),
    # Metal (check before rock)
    (r'\b(metal|doom|sludge|stoner)\b', 'Metal'),
    # Pop/Indie Pop
    (r'\b(pop)\b', 'Pop'),
    # Experimental
    (r'\b(experimental|noise|avant-garde|ambient|synth)\b', 'Experimental'),
    # Rock (broad catch-all)
    (r'\b(rock|grunge|shoegaze|garage|indie|psych|slowcore|jam band|surf)\b', 'Rock'),
    # Jazz (catch remaining)
    (r'\bjazz\b', 'Jazz'),
    # Blues catch remaining
    (r'\bblues\b', 'Blues'),
]

# Manual overrides for tricky cases
OVERRIDES = {
    'children\'s music': 'Other',
    'children\'s, pop': 'Other',
    'fire spinning, flow performance': 'Other',
    'world music': 'Other',
    'comedic musical, multi-genre': 'Other',
    'comedic showtune, experimental': 'Experimental',
    'instrumental': 'Rock',
    'acoustic cat-rock': 'Rock',
    'acoustic ska': 'Rock',
    'punk polka': 'Punk',
    'soul, power trio': 'Funk/Soul/R&B',
    'jazz-influenced funk': 'Funk/Soul/R&B',
    'jazz, funk, folk': 'Funk/Soul/R&B',
    'pop and funk': 'Funk/Soul/R&B',
    'soul, R&B, jazz, blues, rock, funk, gospel, pop, hip-hop': 'Funk/Soul/R&B',
    'soul, R&B, funk, jazz': 'Funk/Soul/R&B',
    'soul, funk': 'Funk/Soul/R&B',
    'hip-hop, house, electro, dance': 'Electronic/DJ',
    'house, disco, funk, techno': 'Electronic/DJ',
    'electronic, dance': 'Electronic/DJ',
    'electronic, avant-garde': 'Electronic/DJ',
    'experimental, electronic': 'Electronic/DJ',
    'experimental electronic': 'Electronic/DJ',
    'experimental synth': 'Experimental',
    'experimental, synth': 'Experimental',
    'big band jazz': 'Jazz',
    'jazz-rock fusion': 'Jazz',
    'alt-folk, bluegrass, jazz': 'Folk/Americana',
    'bluegrass, folk, country, gypsy jazz': 'Folk/Americana',
    'folk, bluegrass, gospel, jazz, punk, blues': 'Folk/Americana',
    'folk, Americana, Celtic, semi-classical': 'Folk/Americana',
    'folk, alt-country, rock, indie': 'Folk/Americana',
    'roots-rock with blues, reggae, Irish, bluegrass, hip-hop, country, folk': 'Folk/Americana',
    'folk, blues, country, bluegrass': 'Folk/Americana',
    'folk, country, bluegrass': 'Folk/Americana',
    'country-folk, Americana': 'Folk/Americana',
    'blues and neo-folk': 'Folk/Americana',
    'blues, Americana, singer-songwriter': 'Folk/Americana',
    'psychedelic country': 'Folk/Americana',
    'country-folk, indie-folk': 'Folk/Americana',
    'folk and country punk': 'Folk/Americana',
    'shanty-rock, jazz-pirate, maritime folk': 'Folk/Americana',
    '1930s-1940s American roots, old-time string band, Western swing': 'Folk/Americana',
    'Appalachian fiddle/Americana': 'Folk/Americana',
    'Americana and pop': 'Folk/Americana',
    'Americana, heartland rock': 'Folk/Americana',
    'classic rock, country': 'Rock',
    'classic rock, jazz fusion, soul, roots': 'Rock',
    'rock, blues, ska, funk, alternative, indie, jazz': 'Rock',
    'rock, blues, country': 'Rock',
    'rock, blues, grunge': 'Rock',
    'rock and blues': 'Rock',
    'rock (90s grunge, 2000s pop-punk, modern indie)': 'Rock',
    'rock (indie, psych-blues, lounge-rock)': 'Rock',
    'dirt road rock / blues roots-rock': 'Rock',
    'jam band with surf-rock, blues, jazz, folk': 'Rock',
    'groove, jazz, folk, doom, surf rock': 'Rock',
    'heavy metal, garage grunge, psychedelic blues': 'Metal',
    'industrial noise, metal': 'Metal',
    'doom metal / swamp metal': 'Metal',
    'bummer metal (stoner, doom, sludge)': 'Metal',
    'heavy metal / thrashing rock': 'Metal',
    'hard rock and metal': 'Metal',
    'instrumental metal (sludge and hardcore)': 'Metal',
    'metal-fusion': 'Metal',
    'punk rock, lo-fi sludge-metal': 'Punk',
    'post-hardcore, punk': 'Punk',
    'punk, grunge, Midwest emo': 'Punk',
    'punk rock, melodic hardcore': 'Punk',
    'post-Midwest mathcore': 'Punk',
    'anarcho political crust': 'Punk',
    'garage rock, punk, psych-rock': 'Rock',
    'alt-garage rock with punk edge': 'Rock',
    'Nordic fusion of indie, crossover prog, and world music': 'Rock',
    'space folk, indie rock, pop, country': 'Folk/Americana',
    'pop-folk, rock': 'Folk/Americana',
    'Midwest emo with pop influences': 'Rock',
    'pop punk, prog rock, alternative acoustic': 'Rock',
    'soft and modern rock with 90s alternative influences': 'Rock',
    'alternative rock with post-punk flair': 'Rock',
    'psychobilly, Americana-roots rock': 'Rock',
    'slime pop': 'Pop',
    'synthy pop-punk': 'Punk',
    'easycore pop-punk rock': 'Punk',
    'glam-punk': 'Punk',
    'country-pop': 'Pop',
    'indie-pop rock': 'Pop',
    'piano-driven indie rock': 'Rock',
    'distorted indie rock': 'Rock',
    'post-neo-janglecore indie rock': 'Rock',
    'indie/surf rock': 'Rock',
    'indie rock / Americana-meets-70s janglecore': 'Rock',
    'horn rock': 'Rock',
    'art punk': 'Punk',
    'techno, EDM': 'Electronic/DJ',
    'techno, electronic dance music': 'Electronic/DJ',
}

# Null genre inferences
NULL_INFERENCES = {
    '#theindianheadband': 'Folk/Americana',
    'Mae and Justine': 'Folk/Americana',
}

def categorize(genre_str):
    if genre_str is None:
        return None
    if genre_str in OVERRIDES:
        return OVERRIDES[genre_str]
    lower = genre_str.lower()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, lower):
            return category
    return 'Other'

with open('/Users/graham/Projects/homegrown/homegrown_2026_acts.json') as f:
    data = json.load(f)

uncategorized = []
for act in data['acts']:
    if act.get('type') != 'band_set':
        continue
    genre = act.get('genre')
    if genre is None and act['name'] in NULL_INFERENCES:
        act['genre_category'] = NULL_INFERENCES[act['name']]
    else:
        cat = categorize(genre)
        act['genre_category'] = cat
        if cat == 'Other' and genre not in ('children\'s music', 'children\'s, pop', 'fire spinning, flow performance', 'world music', 'comedic musical, multi-genre'):
            uncategorized.append((act['name'], genre))

if uncategorized:
    print("UNCATEGORIZED:")
    for name, genre in uncategorized:
        print(f"  {name}: {genre}")

# Count distribution
cats = {}
for a in data['acts']:
    if a.get('type') != 'band_set':
        continue
    c = a.get('genre_category', '?')
    cats[c] = cats.get(c, 0) + 1
print("\nDistribution:")
for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {count:3d}  {cat}")

with open('/Users/graham/Projects/homegrown/homegrown_2026_acts.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print("\nDone. File updated.")
